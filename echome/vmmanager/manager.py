import libvirt
import pathlib
import logging
import subprocess
import random
import shutil
import time
import xmltodict
import base64
from echome.id_gen import IdGenerator
from echome.config import ecHomeConfig
from commander.qemuimg import QemuImg
from identity.models import User
from images.models import BaseImageModel, GuestImage, UserImage, InvalidImageId
from network.models import VirtualNetwork
from keys.models import UserKey
from keys.exceptions import KeyDoesNotExist
from .models import VirtualMachine, HostMachine
from .instance_definitions import InstanceDefinition
from .cloudinit import CloudInit, CloudInitFailedValidation, CloudInitIsoCreationError
from .xml_generator import XmlGenerator
from .exceptions import *

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
        """Actual method that creates a virtual machine."""
        logger.debug(kwargs)

        # Creating the directory for the virtual machine
        vmdir = self.__generate_vm_path(user.account, vm.instance_id)

        # We need an image id to create our VM!
        if "ImageId" not in kwargs:
            msg = "ImageId was not found in launch configuration. Cannot continue!"
            logger.error(msg)
            raise InvalidLaunchConfiguration(msg)
        
        # Get the image from the image id:
        try:
            image = self.get_image_from_id(kwargs["ImageId"], user)
        except InvalidLaunchConfiguration:
            raise
        
        # Then copy our image to the destination directory
        image_iso_path = self.copy_image(image, vm, vmdir)

        # resize our disk
        logger.debug(f"Resizing image size to {kwargs['DiskSize']}")
        try:
            QemuImg().resize(image_iso_path, kwargs["DiskSize"])
        except Exception as e:
            logger.error(f"Encountered error when running qemu resize. {e}")
            raise LaunchError("Encountered error when running qemu resize.")

        # Determine host to run this VM on:
        try:
            hosts = HostMachine.objects.all()
        except Exception as e:
            logger.exception(e)
            raise 
            
        # Use the first for now
        host = hosts[0]

        # initialize our CloudInit object
        cloudinit = CloudInit(base_dir=vmdir)

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
        
        # Cloud-init for Bridge type networking
        if vnet.type == VirtualNetwork.Type.BRIDGE_TO_LAN:
            logger.debug("New virtual machine is using vnet type BridgeToLan")
            # If the IP is specified, check that the IP is valid for their network
            if private_ip and not vnet.validate_ip(kwargs["PrivateIp"]):
                raise InvalidLaunchConfiguration("Provided Private IP address is not valid for the specified network profile.")
            
            # Generate the Cloudinit Networking config
            logger.debug("CloudInit: Creating network config")
            cloudinit.generate_network_config(vnet, private_ip)

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
        
        # Generate the cloudinit Userdata
        # This includes the public keys and user data scripts if any exist.
        cloudinit.generate_userdata_config(
            vm_id = vm.instance_id,
            public_keys = [pub_key],
            user_data_script = kwargs["UserDataScript"] if "UserDataScript" in kwargs else None
        )
        
        # Finally, the meta-data file
        # Which provides some generic information about our environment.
        cloudinit.generate_metadata(vm.instance_id, ip_addr=private_ip, public_key=key_dict)

        # Validate and create the cloudinit iso
        try:
            cloudinit_iso_path = cloudinit.create_iso()
        except CloudInitFailedValidation:
            raise
        except CloudInitIsoCreationError:
            raise
    
        # VNC?
        metadata = {}
        addtl_options = {}
        if "EnableVnc" in kwargs and kwargs["EnableVnc"]:
            addtl_options, metadata = self.configure_vnc(kwargs["VncPort"] if "VncPort" in kwargs else None)
            
        # Generate VM XML Doc
        logger.debug(f"Generating VM config")
        try:
            xmldoc = XmlGenerator.generate_template(
                vm_id = vm.instance_id,
                vnet = vnet,
                instance_type=instanceType,
                image_path=image_iso_path,
                host=host,
                cloudinit_iso_path=cloudinit_iso_path,
                **addtl_options
            )
        except Exception as e:
            logger.error(f"Error when creating XML template. {e}")
            raise LaunchError("Error when creating XML template.")

        # Create the actual XML template in the vm directory
        with open(f"{vmdir}/vm.xml", 'w') as filehandle:
            logger.debug("Writing virtual machine XML document: vm.xml")
            filehandle.write(xmldoc)

  
        logger.debug("Attempting to define XML with virsh..")
        self.currentConnection.defineXML(xmldoc)
        
        # Ensures our VMs start up when the host reboots
        logger.debug("Setting autostart to 1")
        self.__get_libvirt_domain(vm.instance_id).setAutostart(1)
        
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
                "private_ip": private_ip if private_ip else "",
            }
        }
        vm.storage = {}
        vm.metadata = metadata
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

        logger.debug(f"Successfully created VM: {vm.instance_id} : {vmdir}")
        return vm.instance_id


    def configure_vnc(self, vnc_port:str = None):
        """This will provide a VNC configuration if a VM requests it"""
        logger.debug("Enabling VNC")
        vnc_options = {}
        vnc_options["enable_vnc"] = True

        if vnc_port:
            logger.debug(f"VNC Port also specified: {vnc_port}")
            vnc_options["vnc_port"] = vnc_port

        # Generate a random password
        vnc_passwd = User().generate_secret(16)
        vnc_options["vnc_passwd"] = vnc_passwd

        # TODO: Store in Vault or a proper key store
        metadata = {
            'vnc': {
                'password': str(base64.b64encode(bytes(vnc_passwd, 'utf-8')), 'utf-8')
            }
        }

        return vnc_options, metadata


    def get_image_from_id(self, image_id:str, user:User):
        logger.debug("Determining image metadata..")
        
        # check if it's a user image
        image = None
        try:
            image = UserImage.objects.get(
                account=user.account,
                image_id=image_id,
                deactivated=False
            )
        except UserImage.DoesNotExist:
            logger.debug(f"Did not find User defined image with ID: {image_id}")
            
        try:
            image = GuestImage.objects.get(
                image_id=image_id,
                deactivated=False
            )
        except GuestImage.DoesNotExist:
            logger.debug(f"Did not find Guest defined image with ID: {image_id}")
        
        if image == None:
            msg = "Provided ImageId does not exist."
            logger.error(msg)
            raise InvalidLaunchConfiguration(msg)
        
        return image
    

    def copy_image(self, image:BaseImageModel, vm:VirtualMachine, destination_dir:str) -> str:
        """Copy a guest or user image to the path"""
        img_path = image.image_path
        img_format = image.image_metadata["format"]

        # Create a copy of the VM image
        destination_vm_img = f"{destination_dir}/{vm.instance_id}.{img_format}"
        try:
            logger.debug(f"Copying image: {img_path} TO directory {destination_dir} as {vm.instance_id}.{img_format}")
            shutil.copy2(img_path, destination_vm_img)
        except:
            raise LaunchError("Encountered an error on VM copy. Cannot continue.")

        logger.debug(f"Final image: {destination_vm_img}")
        return destination_vm_img


    def _gen_hostname(self, VmId, IpAddr=None):
        if IpAddr:
            prefix = "ip"
            ip_str = "-".join(IpAddr.split('.'))
            res = f"{prefix}-{ip_str}"
            return res
        
        return VmId
    
    
    def get_instance_configuration(self, vm_id):
        """Returns an object with the configuration details of a defined VM. (dump xml)"""
        domain = self.__get_libvirt_domain(vm_id)
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
        domain = self.__get_libvirt_domain(vm_id)
        if not domain:
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
        """Start an instance (and set autostart to 1 for host reboots)"""
        vm = self.__get_libvirt_domain(vm_id)
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
        """Stop an instance"""
        logger.debug(f"Stopping vm: {vm_id}")
        vm = self.__get_libvirt_domain(vm_id)
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


    def terminate_instance(self, vm_id:str, user:User = None, force:bool = False):
        """Terminate the instance"""
        logger.debug(f"Terminating vm: {vm_id}")
        if force:
            logger.warn("FORCE SET TO TRUE!")

        vm_domain = self.__get_libvirt_domain(vm_id)

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


    def __get_libvirt_domain(self, vm_id):
        """Returns currentConnection object if the VM exists. Returns False if vm does not exist."""
        try:
            return self.currentConnection.lookupByName(vm_id)
        except libvirt.libvirtError as e:
            # Error code 42 = Domain not found
            if (e.get_error_code() == 42):
                return False


    def __generate_vm_path(self, account_id, vm_id):
        """Create a path for the virtual machine files to be created in"""
        vm_path = f"{VM_ROOT_DIR}/{account_id}/{vm_id}"
        logger.debug(f"Generated VM Path: {vm_path}. Creating..")
        try:
            pathlib.Path(vm_path).mkdir(parents=True, exist_ok=False)
            logger.info(f"Created VM Path: {vm_path}")
            return vm_path
        except:
            logger.error("Encountered an error when attempting to generate VM path. Cannot continue.")
            raise


    def __delete_vm_path(self, vm_id:str, user:User):
        """Delete the path for the files"""
        # let's not delete all of the vm's in a user's folder
        if not vm_id or vm_id.strip() == "":
            logger.debug("vm_id empty when calling delete_vm_path. Exiting!")
            return
        
        # If it got created in virsh but still failed, undefine it
        vm = self.__get_libvirt_domain(vm_id)
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
