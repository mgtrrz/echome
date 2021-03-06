import libvirt
import sys
from string import Template
import uuid
import pathlib
import logging
import subprocess
import random
import shutil
import time
import json
import datetime
import yaml
import xmltodict
import platform
import psutil
from sqlalchemy import select, and_
from .database import Database
from .instance_definitions import Instance
from .id_gen import IdGenerator
from .guest_image import GuestImage, UserImage, ImageManager, InvalidImageId
from .vnet import VirtualNetwork, VirtualNetworkObject
from .config import ecHomeConfig
from .commander import QemuImg
from .ssh_keystore import KeyStore, KeyDoesNotExist
from .user import User
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
        self.db = Database()

    def getConnection(self):
        return self.currentConnection

    def closeConnection(self):
        self.currentConnection.close()
    
    def _clean_up(self, user: User, vm_id):
        """Cleans up a virtual machine directory if CLEAN_UP_ON_FAIL is true"""
        if CLEAN_UP_ON_FAIL:
            logging.debug("CLEAN_UP_ON_FAIL set to true. Cleaning up..")
            self.__delete_vm_path(user.account, vm_id)
    
    def create_vm(self, user: User, instanceType:Instance, **kwargs):
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
        logging.debug("Generating vm-id")
        vm_id = IdGenerator.generate()
        self.vm_id_in_process = vm_id
        logging.info(f"Generated vm-id: {vm_id}")

        try:
            result = self._create_virtual_machine(user, vm_id, instanceType, **kwargs)
        except InvalidLaunchConfiguration as e:
            logging.error(f"Launch Configuration error: {e}")
            self._clean_up(user, vm_id)
            raise InvalidLaunchConfiguration(e)
        except LaunchError as e:
            logging.error(f"Launch error: {e}")
            self._clean_up(user, vm_id)
            raise LaunchError(e)
        except Exception as e:
            logging.error(f"Encountered other error: {e}")
            raise Exception(e) from e
        
        return result
    
    def determine_host_details(self):
        # Can we determine if the host is using an AMD or Intel CPU from here?
        pass

    # Set to replace __createInstance
    def _create_virtual_machine(self, user: User, vm_id: str, instanceType:Instance, **kwargs):
        """Actual method that creates a virtual machine.
        
        All of the parameters from create_vm() are passed here in addition to
        vm_id, used to uniquely identify the new VM.
        """        

        logging.debug(kwargs)

        # Creating the directory for the virtual machine
        vmdir = self.__generate_vm_path(user.account, vm_id)

        # Networking
        # For VMs launched with BridgeToLan, we'll need to create a cloudinit
        # network file as we're unable to set a private IP address at build time.
        # It must instead be configured during boot with cloud-init.
        # For all other VMs, we can omit the cloudinit ISOs and use the metadata
        # API.

        # Determine what network profile we're using:
        vn = VirtualNetwork()
        vnet = vn.get_network_by_profile_name(kwargs["NetworkProfile"], user)

        if not vnet:
            raise InvalidLaunchConfiguration("Provided NetworkProfile does not exist.")

        private_ip = kwargs["PrivateIp"] if "PrivateIp" in kwargs else None
        
        cloudinit_iso_path = None
        # Cloud-init
        if vnet.type == "BridgeToLan":
            logging.debug("New virtual machine is using vnet type BridgeToLan")
            # If the IP is specified, check that the IP is valid for their network
            if private_ip and not vnet.validate_ip(kwargs["PrivateIp"]):
                raise InvalidLaunchConfiguration("Provided Private IP address is not valid for the specified network profile.")
            
            # Generate the Cloudinit Networking config
            network_cloudinit_config = self._generate_cloudinit_network_config(vnet, private_ip)
            network_yaml_file_path = f"{vmdir}/network.yaml"
            logging.debug(f"Network cloudinit file path: {network_yaml_file_path}")

            # create the file
            with open(network_yaml_file_path, "w") as filehandle:
                logging.debug("Writing cloudinit yaml: network.yaml")
                filehandle.write(network_cloudinit_config)
        
            # Like with Networking above, BridgeToLan uses ISOs to set cloudinit stuff.
            # Other networking types should use the metadata API.
            logging.debug("Determining if KeyName is present.")
            pub_key = None
            key_dict = None
            if "KeyName" in kwargs and kwargs["KeyName"] is not None:
                logging.debug(f"Checking KeyName: {kwargs['KeyName']}.")
                try:
                    #key_meta = KeyStore.get_key(user, kwargs["KeyName"])
                    keyObj = KeyStore().get(user, kwargs["KeyName"])
                    #pub_key = key_meta[0]["public_key"]
                    pub_key = keyObj.public_key
                    key_dict = {kwargs["KeyName"]: [pub_key]}
                    logging.debug("Got public key from KeyName")
                except KeyDoesNotExist:
                    raise ValueError("Specified SSH Key Name does not exist.")
            
            if "ServiceKey" in kwargs and kwargs["ServiceKey"] is not None:
                try:
                    keyObj = KeyStore().get(user, kwargs["ServiceKey"])
                    svc_pub_key = keyObj.public_key
                    key_dict[kwargs["ServiceKey"]] = [svc_pub_key]
                    logging.debug(f"Adding public key from ServiceKey {kwargs['ServiceKey']}")
                except KeyDoesNotExist:
                    raise ValueError("Error adding service key.")
            
            # Generate the cloudinit Userdata 
            cloudinit_userdata = self._generate_cloudinit_userdata_config(
                VmId=vm_id,
                PublicKey=[pub_key],
                UserDataScript=kwargs["UserDataScript"] if "UserDataScript" in kwargs else None
            )
            cloudinit_yaml_file_path = f"{vmdir}/user-data"
            logging.debug(f"Standard cloudinit file path: {cloudinit_yaml_file_path}")

            with open(cloudinit_yaml_file_path, "w") as filehandle:
                logging.debug("Writing cloudinit userdata file: user-data")
                filehandle.write(cloudinit_userdata)
            
            # Finally, the meta-data file
            cloudinit_metadata = self._generate_cloudinit_metadata(vm_id, IpAddr=private_ip, PublicKey=key_dict)
            cloudinit_metadata_yaml_file_path = f"{vmdir}/meta-data"
            logging.debug(f"Metadata cloudinit file path: {cloudinit_metadata_yaml_file_path}")

            with open(cloudinit_metadata_yaml_file_path, "w") as filehandle:
                logging.debug("Writing cloudinit metadata file: meta-data")
                filehandle.write(cloudinit_metadata)

        
            # Validate and create the cloudinit iso
            cloudinit_iso_path = self.__create_cloudinit_iso(vmdir, cloudinit_yaml_file_path, network_yaml_file_path, cloudinit_metadata_yaml_file_path)

        
        # Machine Image
        # Determining the image to use for this VM
        # Is this a guest image or a user-created virtual machine image?
        logging.debug("Determining image metadata..")
        manager = ImageManager()
        if "ImageId" not in kwargs:
            msg = "ImageId was not found in launch configuration. Cannot continue!"
            logging.error(msg)
            raise InvalidLaunchConfiguration(msg)

        try:
            logging.debug(f"Grabbing image metadata from {kwargs['ImageId']}")
            img = manager.getImage("guest", kwargs['ImageId']) #TODO: Check if user image also
        except InvalidImageId as e:
            logging.error(e)
            raise InvalidLaunchConfiguration(e)
        
        img_path = img.guest_image_path
        img_format = img.guest_image_metadata["format"]

        # Create a copy of the VM image
        destination_vm_img = f"{vmdir}/{vm_id}.{img_format}"
        try:
            logging.debug(f"Copying image: {img_path} TO directory {vmdir} as {vm_id}.{img_format}")
            shutil.copy2(img_path, destination_vm_img)
        except:
            raise LaunchError("Encountered an error on VM copy. Cannot continue.")

        logging.debug(f"Final image: {destination_vm_img}")


        # Define XML template
        # If we're using a customXML (usually for debugging), specify it.
        # Otherwise, use the XML that's set in the InstanceType.
        if "CustomXML" in kwargs:
            logging.debug(f"Custom XML defined: {kwargs['CustomXML']}")
            xml_template = kwargs['CustomXML']
        else:
            xml_template = instanceType.get_xml_template()

        # Generate VM
        logging.debug(f"Generating VM config")
        try:
            xmldoc = self._generate_xml_template(
                VmId=vm_id,
                XmlTemplate=xml_template,
                vnet=vnet,
                Cpu=instanceType.get_cpu(), 
                Memory=instanceType.get_memory(), 
                VmImg=destination_vm_img,
                CloudInitIso=cloudinit_iso_path
            )
        except Exception as e:
            logging.error(f"Error when creating XML template. {e}")
            raise LaunchError("Error when creating XML template.")

        # Create the actual XML template in the vm directory
        with open(f"{vmdir}/vm.xml", 'w') as filehandle:
            logging.debug("Writing virtual machine XML document: vm.xml")
            filehandle.write(xmldoc)

        # Disk resize
        qimg = QemuImg()
        logging.debug(f"Resizing image size to {kwargs['DiskSize']}")
        try:
            qimg.resize(destination_vm_img, kwargs["DiskSize"])
        except Exception as e:
            logging.error(f"Encountered error when running qemu resize. {e}")
            raise LaunchError("Encountered error when running qemu resize.")

        
        logging.debug("Attempting to define XML with virsh..")
        self.currentConnection.defineXML(xmldoc)
        
        logging.debug("Setting autostart to 1")
        domain = self.__get_virtlib_domain(vm_id)
        domain.setAutostart(1)
        
        logging.info("Starting VM..")
        self.startInstance(vm_id)

        # Add the information for this VM in the db
        stmt = self.db.user_instances.insert().values(
            account = user.account,
            instance_id = vm_id,
            host = "localhost",
            instance_type = instanceType.itype,
            instance_size = instanceType.isize,
            account_user = user.user_id,
            attached_interfaces = {
                "config_at_launch": {
                    "vnet_id": vnet.vnet_id,
                    "type": vnet.type,
                    "private_ip": kwargs["PrivateIp"] if "PrivateIp" in kwargs else "",
                }
            },
            attached_storage = {},
            key_name = kwargs["KeyName"] if "KeyName" in kwargs else "",
            assoc_firewall_rules = {},
            vm_image_metadata = {
                "image_id": kwargs["ImageId"],
                "image_name": img.name,
            },
            tags = kwargs["Tags"] if "Tags" in kwargs else {},
        )
        logging.debug(stmt)
        result = self.db.connection.execute(stmt)
        logging.debug(result)
        print(f"Successfully created VM: {vm_id} : {vmdir}")
        return vm_id
    
    def _generate_cloudinit_network_config(self, vnet: VirtualNetworkObject, priv_ip_addr=None):
        """Generate Cloudinit network config yaml

        Generates a network cloudinit config. This is meant to be used for BridgeToLan VMs
        where network information isn't set at VM build time but must instead be determined/
        set during boot with a Cloudinit script. VMs that use other network types should be
        able to set network configuration either through XML definition, virsh network
        interfaces, or possibly set through the metadata api.

        :param vnet: VirtualNetwork object where the virtual machine will be launched in. The vnet
            object will fill in details such as the gateway and DNS servers.
        :type vnet: VirtualNetworkObject
        :param priv_ip_addr: Private IP address, defaults to None. If an IP address is not provided
            dhcp4 will be set to True. The Private IP address is not tested if it's valid for this
            network, please perform the check before calling this function.
        :type priv_ip_addr: str, optional
        :return: Cloudinit yaml 
        :rtype: str
        """        
        if vnet.type != "BridgeToLan":
            # Other network types should use the metadata API
            logging.debug("Tried to create cloudinit network config for non-BridgeToLan VM")
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
            logging.debug("UserData script is included in request, making multipart file..")
            sub_messages = []
            format = 'x-shellscript'
            sub_message = MIMEText(UserDataScript, format, sys.getdefaultencoding())
            sub_message.add_header('Content-Disposition', 'attachment; filename="shellscript.sh"')
            content_type = sub_message.get_content_type().lower()
            if content_type not in KNOWN_CONTENT_TYPES:
                logging.warning(f"WARNING: content type {content_type} may be incorrect!")
            sub_messages.append(sub_message)


            format = 'cloud-config'
            sub_message = MIMEText(yaml_config, format, sys.getdefaultencoding())
            sub_message.add_header('Content-Disposition', 'attachment; filename="userdata.yaml"')
            content_type = sub_message.get_content_type().lower()
            if content_type not in KNOWN_CONTENT_TYPES:
                logging.warning(f"WARNING: content type {content_type} may be incorrect!")
            sub_messages.append(sub_message)


            combined_message = MIMEMultipart()
            for msg in sub_messages:
                combined_message.attach(msg)
            logging.debug(combined_message)
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
    
    # Required: VmId, XmlTemplate, vnet:VirtualNetworkObject, Cpu, Memory, VmImg
    # Optional: CloudInitIso
    def _generate_xml_template(self, VmId, XmlTemplate, vnet: VirtualNetworkObject, **kwargs):
        """Generates the XML template for use with defining in libvirt.

        This function at the moment utilizes "template" XML documents in the `xml_templates`
        directory. Template() is then used to fill in variables in the XML documents to
        suit the virtual machine.

        In the future, we may consider using XML libraries to properly generate XML docs.

        :param VmId: Virtual Machine Id
        :type VmId: str
        :param XmlTemplate: This is the name of the xml template to use from the `xml_templates` directory.
        :type XmlTemplate: str
        :param vnet: Virtual Network object for determining if a bridge interface should be used.
        :type vnet: VirtualNetworkObject
        :key Cpu: Number of CPUs (threads) to set for this virtual machine
        :type Cpu: str
        :key Memory: Memory value for the virtual machine. Values would be anything that libvirt accepts, 512M, 4G, etc.
        :type Memory: str
        :key VmImg: Path to the root virtual disk for the virtual machine.
        :type VmImg: str
        :key CloudInitIso: Path to the location of the cloudinit iso for this virtual machine, defaults to None. 
            If attached, the XML document will add a virtual disk with a mount to the cloudinit iso. 
        :type CloudInitIso: str

        :return: XML document as a string
        :rtype: str
        """        
        cloudinit_xml = ""
        
        # Generate Cloudinit disk device IF CloudInit is used.
        if "CloudInitIso" in kwargs:
            with open(f"{XML_TEMPLATES_DIR}/cloudinit_disk.xml", 'r') as filehandle:
                cloudinit_xml = Template(filehandle.read())
                replace = {
                    'VM_USER_CLOUDINIT_IMG_PATH': kwargs["CloudInitIso"]
                }
                cloudinit_xml = cloudinit_xml.substitute(replace)

        # Generate the rest of the VM XML
        with open(f"{XML_TEMPLATES_DIR}/{XmlTemplate}", 'r') as filehandle:
            src = Template(filehandle.read())

        replace = {
            'VM_NAME': VmId,
            'VM_CPU_COUNT': kwargs["Cpu"], 
            'VM_MEMORY': kwargs["Memory"],
            'CLOUDINIT_DISK': cloudinit_xml,
            'VM_USER_IMG_PATH': kwargs["VmImg"],
            'SMBIOS_MODE': '',
            'SMBIOS_BODY': '',
            'BRIDGE_INTERFACE': '',
        }

        if vnet.type == "BridgeToLan":
            # If it is BridgeToLan, we need to add the appropriate bridge interface into the XML
            # template
            replace['BRIDGE_INTERFACE'] = f"""  <interface type="bridge">
<source bridge="{vnet.config['bridge_interface']}"/>
</interface>"""
        
        else:
            # If the new VM is not using the BridgeToLan network type, add smbios
            # information for it to use the metadata service.
            ech = ecHomeConfig.EcHome()
            metadata_api_url = f"{ech.metadata_api_url}:{ech.metadata_api_port}/{VmId}/"
            logging.debug(f"Generated Metadata API url: {metadata_api_url}")
            with open(f"{XML_TEMPLATES_DIR}/smbios.xml", 'r') as filehandle:
                smbios_body_src = Template(filehandle.read())

            replace['SMBIOS_MODE'] = "<smbios mode='sysinfo'/>"
            replace['SMBIOS_BODY'] = smbios_body_src.substitute({
                'NOCLOUD_URL': metadata_api_url
            })
        
        logging.debug("Replacing variables in XML..")
        logging.debug(replace)
        return src.substitute(replace)

    
    # Get information about a instance/VM
    def getInstanceMetadata(self, user_obj, vm_id):

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
        logging.debug(select_stmt)
        rows = self.db.connection.execute(select_stmt).fetchall()
        if rows:
            return rows[0]
        else:
            return None
    
    # Returns an object with the configuration details of a defined VM. (dump xml)
    # Can optionally return the raw XML string
    def getInstanceConfiguration(self, vm_id):
        domain = self.__get_virtlib_domain(vm_id)
        xmldoc = domain.XMLDesc()
        xmltodict.parse(xmldoc)
    
    # Returns all instances belonging to the account/user
    def getAllInstances(self, user_obj):
        columns = [
            self.db.user_instances.c.created,
            self.db.user_instances.c.instance_id,
            self.db.user_instances.c.instance_type,
            self.db.user_instances.c.instance_size,
            self.db.user_instances.c.vm_image_metadata,
            self.db.user_instances.c.account_user,
            self.db.user_instances.c.attached_interfaces,
            self.db.user_instances.c.attached_storage,
            self.db.user_instances.c.key_name,
            self.db.user_instances.c.assoc_firewall_rules,
            self.db.user_instances.c.tags
        ]
        select_stmt = select(columns).where(self.db.user_instances.c.account == user_obj.account)
        rows = self.db.connection.execute(select_stmt).fetchall()
        instances = []
        if rows:
            for row in rows:
                instance = {}
                i = 0
                for col in columns:
                    if col.name == "created":
                        instance[col.name] = str(row[i])
                    else:
                        instance[col.name] = row[i]
                    i += 1

                state, state_int, _  = self.getVmState(instance["instance_id"])
                instance["state"] = {
                    "code": state_int,
                    "state": state,
                }
                instances.append(instance)
        return instances

    def createVirtualMachineImage(self, user, vm_id):

        account_id = user.account
        vm_name = f"{vm_id}.qcow2" # TODO: CHANGE THIS TO ACTUAL MACHINE IMAGE FILE
        vmi_id = IdGenerator.generate("vmi")

        logging.debug(f"Creating VMI from {vm_id}")
        # Instance needs to be turned off to create an image
        logging.debug(f"Stopping {vm_id}")
        self.stopInstance(vm_id)


        user_vmi_dir = f"{VM_ROOT_DIR}/{account_id}/user_vmi"
        # Create it if doesn't exist
        pathlib.Path(user_vmi_dir).mkdir(parents=True, exist_ok=True)
        current_image_full_path = f"{VM_ROOT_DIR}/{account_id}/{vm_id}/{vm_name}"
        new_image_full_path = f"{user_vmi_dir}/{vmi_id}.qcow2"

        try:
            logging.debug(f"Copying image: {vm_name} TO {vmi_id}")
            #shutil.copy2(f"{VM_ROOT_DIR}/{account_id}/{vm_id}/{vm_name}", new_image_full_path)
        except:
            logging.error("Encountered an error on VM copy. Cannot continue.")
            raise
        
        output = self.__run_command(["/usr/bin/qemu-img", "convert", "-O", "qcow2", current_image_full_path, new_image_full_path])
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")

        logging.debug(f"Running Sysprep on: {new_image_full_path}")
        output = self.__run_command(["sudo", "/usr/bin/virt-sysprep", "-a", new_image_full_path])
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")

        logging.debug(f"Running Sparsify on: {new_image_full_path}")
        self.__run_command(["sudo", "/usr/bin/virt-sparsify", "--in-place", new_image_full_path])
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")


        
        return {"vmi_id": vmi_id}

    def getVmState(self, vm_id):
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

        
    def startInstance(self, vm_id):
        vm = self.__get_virtlib_domain(vm_id)
        if not vm:
            return {
                "success": False,
                "meta_data": {},
                "reason": f"VM {vm_id} does not exist",
            }

        if vm.isActive():
            logging.info(f"VM '{vm_id}' already started")

        while not vm.isActive():
            logging.info(f"Starting VM '{vm_id}'")
            vm.create()
        
        return {
            "success": True,
            "meta_data": {},
            "reason": "",
        }
    
    def stopInstance(self, vm_id):
        logging.debug(f"Stopping vm: {vm_id}")
        vm = self.__get_virtlib_domain(vm_id)
        if not vm:
            return {
                "success": False,
                "meta_data": {},
                "reason": f"VM {vm_id} does not exist",
            }

        if not vm.isActive():
            logging.info(f"VM '{vm_id}' already stopped")
            return 

        if vm.isActive():
            print(f"Stopping VM '{vm_id}'")
        else:
            print(f"VM '{vm_id}' is already stopped")

        vm_force_stop_time = 240
        seconds_waited = 0
        while vm.isActive():
            try:
                vm.shutdown()
                time.sleep(1)
                seconds_waited += 1
                if seconds_waited >= vm_force_stop_time:
                    logging.warning(f"Timeout was reached and VM '{vm_id}' hasn't stopped yet. Force shutting down...")
                    vm.destroy()
            except libvirt.libvirtError as e:
                # Error code 55 = Not valid operation: domain is not running
                if (e.get_error_code() == 55):
                    pass
                else:
                    raise(e)

        return {
            "success": True,
            "meta_data": {},
            "reason": "",
        }

    def get_instance_metadata_by_ip(self, ip):
        select_stmt = select(self.db.user_instances.c).where(
            self.db.user_instances.c.attached_interfaces["config_at_launch", "private_ip"].astext == ip
        )
        rows = self.db.connection.execute(select_stmt).fetchall()
        return rows[0]


    # Terminate the instance 
    def terminateInstance(self, user_obj, vm_id):
        logging.debug(f"Terminating vm: {vm_id}")
        account_id = user_obj.account

        vm = self.__get_virtlib_domain(vm_id)
        if not vm:

            # Check to see if it's in the database
            select_stmt = select([self.db.user_instances]).where(
                and_(
                    self.db.user_instances.c.account == user_obj.account, 
                    self.db.user_instances.c.instance_id == vm_id
                )
            )
            rows = self.db.connection.execute(select_stmt).fetchall()

            if rows:
                del_stmt = self.db.user_instances.delete().where(self.db.user_instances.c.instance_id == vm_id)
                self.db.connection.execute(del_stmt)
                return {
                    "success": True,
                    "meta_data": {},
                    "reason": f"Cleaned up fragmaneted VM {vm_id}.",
                }
            else:
                return {
                    "success": False,
                    "meta_data": {},
                    "reason": f"VM {vm_id} does not exist",
                }
        try:
            # Stop the instance
            self.stopInstance(vm_id)
            # Undefine it to remove it from virt
            vm.undefine()
        except libvirt.libvirtError as e:
            logging.error(f"Could not terminate instance {vm_id}: libvirtError {e}")
            return {
                "success": False,
                "meta_data": {},
                "reason": f"Could not terminate instance {vm_id}: libvirtError {e}",
            }
        
        # Delete folder/path
        self.__delete_vm_path(account_id, vm_id)

        # delete entry in db
        del_stmt = self.db.user_instances.delete().where(self.db.user_instances.c.instance_id == vm_id)
        self.db.connection.execute(del_stmt)

        return {
            "success": True,
            "meta_data": {},
            "reason": "",
        }

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
        logging.debug("Validating Cloudinit config yaml.")        
        output = self.__run_command(['cloud-init', 'devel', 'schema', '--config-file', cloudinit_yaml_file_path])
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")

        if cloudinit_network_yaml_file_path:
            logging.debug("Validating Cloudinit Network config yaml.")
            output = self.__run_command(['cloud-init', 'devel', 'schema', '--config-file', cloudinit_network_yaml_file_path])
            if output["return_code"] is not None:
                # There was an issue with the resize
                #TODO: Condition on error
                print("Return code not None")


        # Create cloud_init disk image
        cloudinit_iso_path = f"{vmdir}/cloudinit.iso"

        args = ['cloud-localds', '-v', cloudinit_iso_path, cloudinit_yaml_file_path]

        if cloudinit_metadata_file_path:
            args.append(cloudinit_metadata_file_path)

        if cloudinit_network_yaml_file_path:
            args.append(f"--network-config={cloudinit_network_yaml_file_path}")

        output = self.__run_command(args)
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")

        logging.debug(f"Created cloudinit iso: {cloudinit_iso_path}")

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
        logging.debug(f"Generated VM Path: {vm_path}. Creating..")
        try:
            pathlib.Path(vm_path).mkdir(parents=True, exist_ok=False)
            logging.info(f"Created VM Path: {vm_path}")
            return vm_path
        except:
            logging.error("Encountered an error when attempting to generate VM path. Cannot continue.")
            raise

    # Delete the path for the files
    def __delete_vm_path(self, account_id, vm_id):
        # let's not delete all of the vm's in a user's folder
        if not vm_id:
            logging.debug("vm_id empty when calling delete_vm_path. Exiting!")
            return
        
        # If it got created in virsh but still failed, undefine it
        vm = self.__get_virtlib_domain(vm_id)
        if vm:
            vm.undefine()

        path = f"{VM_ROOT_DIR}/{account_id}/{vm_id}"
        logging.debug(f"Deleting VM Path: {path}")

        try:
            shutil.rmtree(path)
        except:
            logging.error("Encountered an error when atempting to delete VM path.")

    def __run_command(self, cmd: list):
        logging.debug("Running command: ")
        logging.debug(cmd)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
        output = process.stdout.readline()
        logging.debug(output.strip())
        return_code = process.poll()
        logging.debug(f"SUBPROCESS RETURN CODE: {return_code}")
        return {
            "return_code": return_code,
            "output": output,
        }

class InstanceConfiguration():
    def __init__(self, vm_id, **kwargs):
        self.id = vm_id


class InvalidLaunchConfiguration(Exception):
    pass

class LaunchError(Exception):
    pass
