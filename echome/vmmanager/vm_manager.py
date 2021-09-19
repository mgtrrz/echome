import libvirt
import sys
from string import Template
import pathlib
import logging
import subprocess
import random
import shutil
import time
import json
# import datetime
import yaml
import xmltodict
# import platform
# import psutil
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from echome.id_gen import IdGenerator
from echome.config import ecHomeConfig
from commander.qemuimg import QemuImg
from commander.cloudinit import CloudInit
from commander.cloudlocalds import CloudLocalds
from identity.models import User
from images.models import GuestImage, UserImage, InvalidImageId
from network.models import VirtualNetwork
from .models import HostMachine, VirtualMachine, UserKey, KeyDoesNotExist
from .instance_definitions import InstanceDefinition
from .xml_generator import XmlGenerator

logger = logging.getLogger(__name__)

KNOWN_CONTENT_TYPES = [
    'text/x-include-once-url',
    'text/x-include-url',
    'text/cloud-config-archive',
    'text/upstart-job',
    'text/cloud-config',
    'text/part-handler',
    'text/x-shellscript',
    'text/cloud-boothook',
]


VM_ROOT_DIR = ecHomeConfig.VirtualMachines().user_dir
XML_TEMPLATES_DIR = f"{ecHomeConfig.EcHome().base_dir}/xml_templates"

# if at any point during the VM Creation process fails,
# clean up after itself. Useful to disable for debugging,
# But keep this to True to avoid having a lot of directories
# and files wasting space for non-functioning VMs
CLEAN_UP_ON_FAIL = True

# Flow for VM Creation
# 1. Generate a VM Id
# 2. Generate the cloudinit config
#   a. Save the cloudinit config to a temporary folder
#   b. validate the file
#   c. create an disk img for the cloudinit file
# 3. Generate the VM XML document
# 4. Launch new VM with XML document

class VmManager:

    def __init__(self):
        self.currentConnection = libvirt.open('qemu:///system')

    def getConnection(self):
        return self.currentConnection

    def closeConnection(self):
        self.currentConnection.close()
    
    def _clean_up(self, user:User, vm_id:str):
        """Cleans up a virtual machine directory if CLEAN_UP_ON_FAIL is true"""
        if CLEAN_UP_ON_FAIL:
            logging.debug("CLEAN_UP_ON_FAIL set to true. Cleaning up..")
            self.__delete_vm_path(vm_id, user)
    
    def create_vm(self, user: User, instanceType:InstanceDefinition, **kwargs):
        """Create a virtual machine
        This function does not create the VM but instead passes all of the
        arguments to the internal function _create_virtual_machine(). If this 
        process fails, the function will clean up after itself. Set CLEAN_UP_ON_FAIL
        to False to alter this behavior to keep files for debugging purposes.
        :param user: User object for identifying which account the VM is created for.
        :type user: User
        :param instanceType: Instance type for the virtual machine to use.
        :type instanceType: Instance
        :key NetworkProfile: Network profile to use for the virtual machine. Use the profile name.
        :type NetworkProfile: str
        :key ImageId: Guest or User image ID to spawn the virtual machine from.
        :type ImageId: str
        :key DiskSize: Disk size for the virtual machine. (e.g. 10G, 200G, 10000M)
        :type DiskSize: str
        :key KeyName: Name of the SSH Keystore item to add a public ssh key to the VM. Defaults to None.
        :type KeyName: str
        :key PrivateIp: Private IP address to assign. Defaults to None.
        :type PrivateIp: str
        :key CustomXML: Specify a custom XML file (located in xml_templates) to launch the VM from. Defaults to None.
        :type CustomXML: str
        :key UserDataScript: User-data shell script to boot the instance with. Defaults to none.
        :type UserDataScript: str
        :key Tags: Dictionary of tags to apply to this instance. Defaults to None
        :type Tags: dict
        :key ServiceKey: Name of the SSH Keystore item for a ecHome service. This should not be set by a user. Defaults to None.
        :type KeyName: str
        :raises InvalidLaunchConfiguration: If supplied arguments are invalid for this virtual machine.
        :raises LaunchError: If there was an error during build of the virtual machine.
        :return: Virtual machine ID if successful.
        :rtype: str
        """
        # Create the vm id to pass into the other functions
        logger.debug("Generating vm-id")
        new_instance = VirtualMachine()
        new_instance.generate_id()

        self.vm_id_in_process = new_instance.instance_id
        logger.info(f"Generated vm-id: {new_instance.instance_id}")

        try:
            result = self._create_virtual_machine(user, new_instance, instanceType, **kwargs)
        except InvalidLaunchConfiguration as e:
            logger.error(f"Launch Configuration error: {e}")
            self._clean_up(user, new_instance.instance_id)
            raise
        except LaunchError as e:
            logger.exception(f"Launch error: {e}")
            self._clean_up(user, new_instance.instance_id)
            raise
        except Exception as e:
            logger.exception(f"Encountered other error: {e}")
            raise
        
        return result
    
    def determine_host_details(self):
        # Can we determine if the host is using an AMD or Intel CPU from here?
        pass

    # Set to replace __createInstance
    def _create_virtual_machine(self, user: User, vm:VirtualMachine, instanceType:InstanceDefinition, **kwargs):
        """Actual method that creates a virtual machine.
        
        All of the parameters from create_vm() are passed here in addition to
        vm_id, used to uniquely identify the new VM.
        """        

        logger.debug(kwargs)

        # Creating the directory for the virtual machine
        vmdir = self.__generate_vm_path(user.account, vm.instance_id)

        # Determine host to run this VM on:
        try:
            hosts = HostMachine.objects.all()
        except Exception as e:
            logger.exception(e)
            raise 
            
        # Use the first for now
        host = hosts[0]

        # Networking
        # For VMs launched with BridgeToLan, we'll need to create a cloudinit
        # network file as we're unable to set a private IP address at build time.
        # It must instead be configured during boot with cloud-init.
        # For all other VMs, we can omit the cloudinit ISOs and use the metadata
        # API.

        # Determine what network profile we're using:
        try:
            vnet = VirtualNetwork.objects.get(
                name=kwargs["NetworkProfile"],
                account=user.account
            )
        except VirtualNetwork.DoesNotExist:
            raise InvalidLaunchConfiguration("Provided NetworkProfile does not exist.")

        private_ip = kwargs["PrivateIp"] if "PrivateIp" in kwargs else None
        
        cloudinit_iso_path = None
        # Cloud-init
        if vnet.type == VirtualNetwork.Type.BRIDGE_TO_LAN:
            logger.debug("New virtual machine is using vnet type BridgeToLan")
            # If the IP is specified, check that the IP is valid for their network
            if private_ip and not vnet.validate_ip(kwargs["PrivateIp"]):
                raise InvalidLaunchConfiguration("Provided Private IP address is not valid for the specified network profile.")
            
            # Generate the Cloudinit Networking config
            network_cloudinit_config = self._generate_cloudinit_network_config(vnet, private_ip)
            network_yaml_file_path = f"{vmdir}/network.yaml"
            logger.debug(f"Network cloudinit file path: {network_yaml_file_path}")

            # create the file
            with open(network_yaml_file_path, "w") as filehandle:
                logger.debug("Writing cloudinit yaml: network.yaml")
                filehandle.write(network_cloudinit_config)

        elif vnet.type == VirtualNetwork.Type.NAT:
            logger.debug("New virtual machine is using vnet type NAT")

        # Adding SSH key
        logger.debug("Determining if KeyName is present.")
        pub_key = None
        key_dict = None
        if "KeyName" in kwargs and kwargs["KeyName"] is not None:
            logger.debug(f"Checking KeyName: {kwargs['KeyName']}.")
            try:
                keyObj:UserKey = UserKey.objects.get(
                    account=user.account,
                    name=kwargs["KeyName"]
                )

                pub_key = keyObj.public_key
                key_dict = {kwargs["KeyName"]: [pub_key]}
                logger.debug("Got public key from KeyName")
            except UserKey.DoesNotExist:
                raise ValueError("Specified SSH Key Name does not exist.")
        
        # Optional SSH service key (for echome services)
        if "ServiceKey" in kwargs and kwargs["ServiceKey"] is not None:
            try:
                keyObj = KeyStore().get(user, kwargs["ServiceKey"])
                svc_pub_key = keyObj.public_key
                key_dict[kwargs["ServiceKey"]] = [svc_pub_key]
                logger.debug(f"Adding public key from ServiceKey {kwargs['ServiceKey']}")
            except KeyDoesNotExist:
                raise ValueError("Error adding service key.")
            
        # Generate the cloudinit Userdata 
        cloudinit_userdata = self._generate_cloudinit_userdata_config(
            VmId=vm.instance_id,
            PublicKey=[pub_key],
            UserDataScript=kwargs["UserDataScript"] if "UserDataScript" in kwargs else None
        )
        cloudinit_yaml_file_path = f"{vmdir}/user-data"
        logger.debug(f"Standard cloudinit file path: {cloudinit_yaml_file_path}")

        with open(cloudinit_yaml_file_path, "w") as filehandle:
            logger.debug("Writing cloudinit userdata file: user-data")
            filehandle.write(cloudinit_userdata)
        
        # Finally, the meta-data file
        cloudinit_metadata = self._generate_cloudinit_metadata(vm.instance_id, IpAddr=private_ip, PublicKey=key_dict)
        cloudinit_metadata_yaml_file_path = f"{vmdir}/meta-data"
        logger.debug(f"Metadata cloudinit file path: {cloudinit_metadata_yaml_file_path}")

        with open(cloudinit_metadata_yaml_file_path, "w") as filehandle:
            logger.debug("Writing cloudinit metadata file: meta-data")
            filehandle.write(cloudinit_metadata)


        # Validate and create the cloudinit iso
        cloudinit_iso_path = self.__create_cloudinit_iso(vmdir, cloudinit_yaml_file_path, network_yaml_file_path, cloudinit_metadata_yaml_file_path)

    
        # Machine Image
        # Determining the image to use for this VM
        # Is this a guest image or a user-created virtual machine image?
        logger.debug("Determining image metadata..")

        if "ImageId" not in kwargs:
            msg = "ImageId was not found in launch configuration. Cannot continue!"
            logger.error(msg)
            raise InvalidLaunchConfiguration(msg)
        
        # check if it's a user image
        image = None
        try:
            image = UserImage.objects.get(
                account=user.account,
                image_id=kwargs['ImageId'],
                deactivated=False
            )
        except Exception as e:
            logger.debug(e)
            
        try:
            image = GuestImage.objects.get(
                image_id=kwargs['ImageId'],
                deactivated=False
            )
        except Exception as e:
            logger.debug(e)
        
        if image == None:
            msg = "ImageId does not exist."
            logger.error(msg)
            raise InvalidLaunchConfiguration(msg)
        
        img_path = image.image_path
        img_format = image.image_metadata["format"]

        # Create a copy of the VM image
        destination_vm_img = f"{vmdir}/{vm.instance_id}.{img_format}"
        try:
            logger.debug(f"Copying image: {img_path} TO directory {vmdir} as {vm.instance_id}.{img_format}")
            shutil.copy2(img_path, destination_vm_img)
        except:
            raise LaunchError("Encountered an error on VM copy. Cannot continue.")

        logger.debug(f"Final image: {destination_vm_img}")


        # Define XML template
        # If we're using a customXML (usually for debugging), specify it.
        # Otherwise, use the XML that's set in the InstanceType.
        # if "CustomXML" in kwargs:
        #     logger.debug(f"Custom XML defined: {kwargs['CustomXML']}")
        #     xml_template = kwargs['CustomXML']
        # else:
        #     xml_template = instanceType.get_xml_template()

        # Generate VM
        logger.debug(f"Generating VM config")
        try:
            xmldoc = XmlGenerator.generate_template(
                vm_id = vm.instance_id,
                vnet = vnet,
                instance_type=instanceType,
                image_path=destination_vm_img,
                host=host,
                cloudinit_iso_path=cloudinit_iso_path,
            )

        except Exception as e:
            logger.error(f"Error when creating XML template. {e}")
            raise LaunchError("Error when creating XML template.")

        # Create the actual XML template in the vm directory
        with open(f"{vmdir}/vm.xml", 'w') as filehandle:
            logger.debug("Writing virtual machine XML document: vm.xml")
            filehandle.write(xmldoc)

        # Disk resize
        qimg = QemuImg()
        logger.debug(f"Resizing image size to {kwargs['DiskSize']}")
        try:
            qimg.resize(destination_vm_img, kwargs["DiskSize"])
        except Exception as e:
            logger.error(f"Encountered error when running qemu resize. {e}")
            raise LaunchError("Encountered error when running qemu resize.")

        
        logger.debug("Attempting to define XML with virsh..")
        self.currentConnection.defineXML(xmldoc)
        
        # Ensures our VMs start up when the host reboots
        logger.debug("Setting autostart to 1")
        domain = self.__get_virtlib_domain(vm.instance_id)
        domain.setAutostart(1)
        
        logger.info("Starting VM..")
        self.start_instance(vm.instance_id)

        # Add the information for this VM in the db
        vm.account = user.account
        # TODO: Properly assign this
        vm.host = HostMachine.objects.get(name="echome")
        vm.instance_type = instanceType.itype
        vm.instance_size = instanceType.isize
        vm.account = user.account
        vm.interfaces = {
            "config_at_launch": {
                "vnet_id": vnet.network_id,
                "type": vnet.type,
                "private_ip": kwargs["PrivateIp"] if "PrivateIp" in kwargs else "",
            }
        }
        vm.storage = {}
        vm.key_name = kwargs["KeyName"] if "KeyName" in kwargs else ""
        vm.firewall_rules = {}
        vm.image_metadata = {
            "image_id": kwargs["ImageId"],
            "image_name": image.name,
        }
        vm.tags = kwargs["Tags"] if "Tags" in kwargs else {}
        
        logger.debug(vm)
        try:
            vm.save()
        except Exception as e:
            logger.debug(e)
            raise Exception

        print(f"Successfully created VM: {vm.instance_id} : {vmdir}")
        return vm.instance_id
    
    def _generate_cloudinit_network_config(self, vnet: VirtualNetwork, priv_ip_addr=None):
        """Generate Cloudinit network config yaml
        Generates a network cloudinit config. This is meant to be used for BridgeToLan VMs
        where network information isn't set at VM build time but must instead be determined/
        set during boot with a Cloudinit script. VMs that use other network types should be
        able to set network configuration either through XML definition, virsh network
        interfaces, or possibly set through the metadata api.
        :param vnet: VirtualNetwork object where the virtual machine will be launched in. The vnet
            object will fill in details such as the gateway and DNS servers.
        :type vnet: VirtualNetwork
        :param priv_ip_addr: Private IP address, defaults to None. If an IP address is not provided
            dhcp4 will be set to True. The Private IP address is not tested if it's valid for this
            network, please perform the check before calling this function.
        :type priv_ip_addr: str, optional
        :return: Cloudinit yaml 
        :rtype: str
        """

        # Right now, this only works for bridge interfaces
        # When we get NAT working, we'll check for it here too
        if vnet.type != VirtualNetwork.Type.BRIDGE_TO_LAN:
            # Other network types should use the metadata API
            logger.debug("Tried to create cloudinit network config for non-BridgeToLan VM")
            return

        if priv_ip_addr:
            private_ip = f"{priv_ip_addr}/{vnet.config['prefix']}"
            interface = {
                "dhcp4": False,
                "dhcp6": False,
                "addresses": [
                    private_ip
                ],
                "gateway4": vnet.config['gateway'],
                "nameservers": {
                    "addresses": vnet.config['dns_servers']
                }
            }
        else:
            interface = {
                "dhcp4": True,
                "dhcp6": False,
            }

        network_config = {
            "version": 2,
            "ethernets": {
                "ens2": interface
            }
        }

        return yaml.dump(network_config, default_flow_style=False, indent=2, sort_keys=False)
    
    def _generate_cloudinit_userdata_config(self, VmId, PublicKey:list=None, UserDataScript=None):
        """Generate Cloudinit Userdata config yaml
        Generates a basic cloudinit config with hostname and public key entries. The only
        required parameter is the virtual machine Id (VmId). Hostname and PublicKey can
        be left blank.
        :param VmId: Virtual Machine Id. Used to fill the hostname if Hostname is not provided.
        :type VmId: str
        :param PublicKey: Public key to attach to the virtual machine. If not used, no SSH key will
            be provided.
        :type PublicKey: str
        :param UserDataScript: User-data shell script to boot the instance with. Defaults to none.
        :type UserDataScript: str
        :return: YAML cloudinit config
        :rtype: str
        """        

        # If hostname is not supplied, use the vm ID
        config_json = {
            "chpasswd": { "expire": False },
            "ssh_pwauth": False,
        }

        ssh_keys_json = {
            "ssh_authorized_keys": PublicKey if PublicKey is not None else []
        }

        # This is an incredibly hacky way to get json flow style output (retaining {expire: false} in the yaml output)
        # I'm unsure if cloudinit would actually just be happy receiving all YAML input.
        configfile = "#cloud-config\n"
        config_yaml = yaml.dump(config_json, default_flow_style=None, sort_keys=False)
        ssh_keys_yaml = yaml.dump(ssh_keys_json, default_flow_style=False, sort_keys=False, width=1000)

        yaml_config = configfile + config_yaml + ssh_keys_yaml

        if UserDataScript:
            logger.debug("UserData script is included in request, making multipart file..")
            sub_messages = []
            format = 'x-shellscript'
            sub_message = MIMEText(UserDataScript, format, sys.getdefaultencoding())
            sub_message.add_header('Content-Disposition', 'attachment; filename="shellscript.sh"')
            content_type = sub_message.get_content_type().lower()
            if content_type not in KNOWN_CONTENT_TYPES:
                logger.warning(f"WARNING: content type {content_type} may be incorrect!")
            sub_messages.append(sub_message)


            format = 'cloud-config'
            sub_message = MIMEText(yaml_config, format, sys.getdefaultencoding())
            sub_message.add_header('Content-Disposition', 'attachment; filename="userdata.yaml"')
            content_type = sub_message.get_content_type().lower()
            if content_type not in KNOWN_CONTENT_TYPES:
                logger.warning(f"WARNING: content type {content_type} may be incorrect!")
            sub_messages.append(sub_message)


            combined_message = MIMEMultipart()
            for msg in sub_messages:
                combined_message.attach(msg)
            logger.debug(combined_message)
            return str(combined_message)

        return yaml_config
    
    def _generate_cloudinit_metadata(self, VmId, IpAddr=None, Hostname=None, PublicKey:dict=None):
        echmd = ecHomeConfig.EcHomeMetadata()
        md = {
            "instance-id": VmId,
            "local-hostname": Hostname if Hostname else self._gen_hostname(VmId, IpAddr),
            "cloud-name": "ecHome",
            "availability-zone": echmd.availability_zone,
            "region": echmd.region,
            "public-keys": PublicKey if PublicKey else {}
        }

        return json.dumps(md, indent=4)
    
    def _gen_hostname(self, VmId, IpAddr=None):
        if IpAddr:
            prefix = "ip"
            ip_str = "-".join(IpAddr.split('.'))
            res = f"{prefix}-{ip_str}"
            return res
        
        return VmId
    
    
    # Get information about a instance/VM
    def get_instance_metadata(self, user_obj, vm_id):

        select_stmt = select([self.db.user_instances]).where(
            and_(
                self.db.user_instances.c.account == user_obj.account, 
                self.db.user_instances.c.instance_id == vm_id
            )
        )
        rows = self.db.connection.execute(select_stmt).fetchall()
        instances = []
        if rows:
            result = rows[0]
            data = {}
            i = 0
            for col in self.db.user_instances.columns:
                if col.name == "created":
                    data[col.name] = str(result[i])
                else:
                    data[col.name] = result[i]
                i += 1
            # Get instance state
            state, state_int, _  = self.getVmState(vm_id)
            data["state"] = {
                "code": state_int,
                "state": state,
            }
            instances.append(data)

        return instances
    
    def get_anonymous_vm_metadata(self, vm_id=None, ip_addr=None):
        if ip_addr:
            select_stmt = select(self.db.user_instances.c).where(
                self.db.user_instances.c.attached_interfaces["config_at_launch", "private_ip"].astext == ip_addr
            )
        elif vm_id:
            select_stmt = select(self.db.user_instances.c).where(
                self.db.user_instances.c.instance_id == vm_id
            )
        else:
            return None
        logger.debug(select_stmt)
        rows = self.db.connection.execute(select_stmt).fetchall()
        if rows:
            return rows[0]
        else:
            return None
    
    # Returns an object with the configuration details of a defined VM. (dump xml)
    # Can optionally return the raw XML string
    def get_instance_configuration(self, vm_id):
        domain = self.__get_virtlib_domain(vm_id)
        xmldoc = domain.XMLDesc()
        xmltodict.parse(xmldoc)
    

    def create_virtual_machine_image(self, user:User, vm_id:str):

        account_id = user.account
        vm_name = f"{vm_id}.qcow2" # TODO: CHANGE THIS TO ACTUAL MACHINE IMAGE FILE
        vmi_id = IdGenerator.generate("vmi")

        logger.debug(f"Creating VMI from {vm_id}")
        # Instance needs to be turned off to create an image
        logger.debug(f"Stopping {vm_id}")
        self.stop_instance(vm_id)

        user_vmi_dir = f"{VM_ROOT_DIR}/{account_id}/user_vmi"
        # Create it if doesn't exist
        pathlib.Path(user_vmi_dir).mkdir(parents=True, exist_ok=True)
        current_image_full_path = f"{VM_ROOT_DIR}/{account_id}/{vm_id}/{vm_name}"
        new_image_full_path = f"{user_vmi_dir}/{vmi_id}.qcow2"

        try:
            logger.debug(f"Copying image: {vm_name} TO {vmi_id}")
            #shutil.copy2(f"{VM_ROOT_DIR}/{account_id}/{vm_id}/{vm_name}", new_image_full_path)
        except:
            logger.error("Encountered an error on VM copy. Cannot continue.")
            raise
        
        output = self.__run_command(["/usr/bin/qemu-img", "convert", "-O", "qcow2", current_image_full_path, new_image_full_path])
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")

        logger.debug(f"Running Sysprep on: {new_image_full_path}")
        output = self.__run_command(["sudo", "/usr/bin/virt-sysprep", "-a", new_image_full_path])
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")

        logger.debug(f"Running Sparsify on: {new_image_full_path}")
        self.__run_command(["sudo", "/usr/bin/virt-sparsify", "--in-place", new_image_full_path])
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")

        return {"vmi_id": vmi_id}

    def get_vm_state(self, vm_id:str):
        domain = self.__get_virtlib_domain(vm_id)
        if domain:
            state_int, reason = domain.state()

            if state_int == libvirt.VIR_DOMAIN_NOSTATE:
                state_str = "no_state"
            elif state_int == libvirt.VIR_DOMAIN_RUNNING:
                state_str = "running"
            elif state_int == libvirt.VIR_DOMAIN_BLOCKED:
                state_str = "blocked"
            elif state_int == libvirt.VIR_DOMAIN_PAUSED:
                state_str = "paused"
            elif state_int == libvirt.VIR_DOMAIN_SHUTDOWN:
                state_str = "shutdown"
            elif state_int == libvirt.VIR_DOMAIN_SHUTOFF:
                state_str = "shutoff"
            elif state_int == libvirt.VIR_DOMAIN_CRASHED:
                state_str = "crashed"
            elif state_int == libvirt.VIR_DOMAIN_PMSUSPENDED:
                # power management (entered into s3 state)
                state_str = "pm_suspended"
            else:
                state_str = "unknown"
        else:
            state_str = "unknown"
            state_int = 0
            reason = "Unknown state"

        return state_str, state_int, str(reason)

        
    def start_instance(self, vm_id):
        vm = self.__get_virtlib_domain(vm_id)
        if not vm:
            return VirtualMachineDoesNotExist

        if vm.isActive():
            logger.info(f"VM '{vm_id}' already started")
            return True

        logger.info(f"Starting VM '{vm_id}'")
        try:
            vm.create()
        except Exception as e:
            logger.debug(f"Unable to start Virtual Machine {vm_id}: {e}")
            raise VirtualMachineConfigurationException
        
        logger.debug("Setting autostart to 1 for started instances")
        vm.setAutostart(1)
        
        return True
    
    def stop_instance(self, vm_id):
        logger.debug(f"Stopping vm: {vm_id}")
        vm = self.__get_virtlib_domain(vm_id)
        if not vm:
            raise VirtualMachineDoesNotExist

        if not vm.isActive():
            logger.info(f"VM '{vm_id}' already stopped")
            return True
        
        logger.debug("Setting autostart to 0 for stopped instances")
        vm.setAutostart(0)

        vm_force_stop_time = 240
        seconds_waited = 0
        while vm.isActive():
            try:
                vm.shutdown()
                time.sleep(1)
                seconds_waited += 1
                if seconds_waited >= vm_force_stop_time:
                    logger.warning(f"Timeout was reached and VM '{vm_id}' hasn't stopped yet. Force shutting down...")
                    vm.destroy()
            except libvirt.libvirtError as e:
                # Error code 55 = Not valid operation: domain is not running
                if (e.get_error_code() == 55):
                    pass
                else:
                    raise(e)

        return True

    def get_instance_metadata_by_ip(self, ip):
        select_stmt = select(self.db.user_instances.c).where(
            self.db.user_instances.c.attached_interfaces["config_at_launch", "private_ip"].astext == ip
        )
        rows = self.db.connection.execute(select_stmt).fetchall()
        return rows[0]


    # Terminate the instance 
    def terminate_instance(self, vm_id:str, user:User = None, force:bool = False):
        logger.debug(f"Terminating vm: {vm_id}")
        if force:
            logger.warn("FORCE SET TO TRUE!")

        vm_domain = self.__get_virtlib_domain(vm_id)

        try:
            if user:
                vm_db = VirtualMachine.objects.get(
                    instance_id = vm_id,
                    account = user.account
                )
            else:
                vm_db = VirtualMachine.objects.get(
                    instance_id = vm_id
                )
        except Exception as e:
            if not force:
                # Nothing found in DB for this account
                raise VirtualMachineDoesNotExist

        try:
            # Stop the instance
            self.stop_instance(vm_id)
            # Undefine it to remove it from virt
            vm_domain.undefine()
        except VirtualMachineDoesNotExist:
            pass
        except libvirt.libvirtError as e:
            logger.error(f"Could not terminate instance {vm_id}: libvirtError {e}")
            raise VirtualMachineTerminationException()
        
        # Delete folder/path
        if user:
            self.__delete_vm_path(vm_id, user)

        # delete entry in db
        try:
            if vm_db: 
                vm_db.delete()
        except Exception as e:
            raise Exception(f"Unable to delete row from database. instance_id={vm_id}")

        return True

    # Returns currentConnection object if the VM exists. Returns False if vm does not exist.
    def __get_virtlib_domain(self, vm_id):
        try:
            return self.currentConnection.lookupByName(vm_id)
        except libvirt.libvirtError as e:
            # Error code 42 = Domain not found
            if (e.get_error_code() == 42):
                return False

    # Generate an ISO from the cloudinit YAML files
    def __create_cloudinit_iso(self, vmdir, cloudinit_yaml_file_path, cloudinit_network_yaml_file_path=None, cloudinit_metadata_file_path=None):

        # Validate the yaml file
        logger.debug("Validating Cloudinit config yaml.")        
        if not CloudInit().validate_schema(cloudinit_yaml_file_path):
            logger.exception("Failed validating Cloudinit config yaml")
            raise Exception

        # Create cloud_init disk image
        cloudinit_iso_path = f"{vmdir}/cloudinit.iso"

        create_image_success = CloudLocalds().create_image(
            user_data_file=cloudinit_yaml_file_path,
            output=cloudinit_iso_path,
            meta_data_file=cloudinit_metadata_file_path,
            network_config_file=cloudinit_network_yaml_file_path
        )

        if not create_image_success:
            logger.exception("Was not able to create the cloud-init image!")
            raise Exception

        logger.debug(f"Created cloudinit iso: {cloudinit_iso_path}")
        return cloudinit_iso_path

    def __generate_mac_addr(self):
        mac = [ 0x00, 0x16, 0x3e,
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0xff),
            random.randint(0x00, 0xff) ]
        return ':'.join(map(lambda x: "%02x" % x, mac))

    # Create a path for the files to be created in
    def __generate_vm_path(self, account_id, vm_id):
        vm_path = f"{VM_ROOT_DIR}/{account_id}/{vm_id}"
        logger.debug(f"Generated VM Path: {vm_path}. Creating..")
        try:
            pathlib.Path(vm_path).mkdir(parents=True, exist_ok=False)
            logger.info(f"Created VM Path: {vm_path}")
            return vm_path
        except:
            logger.error("Encountered an error when attempting to generate VM path. Cannot continue.")
            raise

    # Delete the path for the files
    def __delete_vm_path(self, vm_id:str, user:User):
        # let's not delete all of the vm's in a user's folder
        if not vm_id or vm_id.strip() == "":
            logger.debug("vm_id empty when calling delete_vm_path. Exiting!")
            return
        
        # If it got created in virsh but still failed, undefine it
        vm = self.__get_virtlib_domain(vm_id)
        if vm:
            vm.undefine()

        path = f"{VM_ROOT_DIR}/{user.account}/{vm_id}"
        logger.debug(f"Deleting VM Path: {path}")

        try:
            shutil.rmtree(path)
        except:
            logger.error("Encountered an error when atempting to delete VM path.")

    def __run_command(self, cmd: list):
        logger.debug("Running command: ")
        logger.debug(cmd)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
        output = process.stdout.readline()
        logger.debug(output.strip())
        return_code = process.poll()
        logging.debug(f"SUBPROCESS RETURN CODE: {return_code}")
        return {
            "return_code": return_code,
            "output": output,
        }

class InstanceConfiguration():
    def __init__(self, vm_id, **kwargs):
        self.id = vm_id

class VirtualMachineDoesNotExist(Exception):
    pass

class VirtualMachineTerminationException(Exception):
    pass

class VirtualMachineConfigurationException(Exception):
    pass

class InvalidLaunchConfiguration(Exception):
    pass

class LaunchError(Exception):
    pass