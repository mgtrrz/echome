import libvirt
import pathlib
import logging
import subprocess
import shutil
import xmltodict
import base64
import os
from typing import List
from echome.config import ecHomeConfig
from commander.qemuimg import QemuImg
from commander.virt_tools import VirtTools
from identity.models import User
from images.models import BaseImageModel, GuestImage, UserImage, InvalidImageId
from network.models import VirtualNetwork
from network.manager import VirtualNetworkManager
from keys.models import UserKey
from .models import VirtualMachine, HostMachine, Volume
from .instance_definitions import InstanceDefinition
from .cloudinit import CloudInit, CloudInitFailedValidation, CloudInitIsoCreationError
from .xml_generator import VirtualMachineInstance
from .exceptions import LaunchError, InvalidLaunchConfiguration, VirtualMachineDoesNotExist, VirtualMachineConfigurationError, ImagePrepError

logger = logging.getLogger(__name__)

VM_ROOT_DIR = ecHomeConfig.VirtualMachines().user_dir

# if at any point during the VM Creation process fails,
# clean up after itself. Useful to disable for debugging,
# But keep this to True to avoid having a lot of directories
# and files wasting space for non-functioning VMs
CLEAN_UP_ON_FAIL = os.getenv("VM_CLEAN_UP_ON_FAIL", 'true').lower() == 'true'

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
        This function does not create the VM but instead passes all of the arguments to the internal
        function _create_virtual_machine(). If this process fails, the function will clean up after
        itself. Set the environment var VM_CLEAN_UP_ON_FAIL to False to alter this behavior to keep
        files for debugging purposes.

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

        # We need an image id to create our VM!
        if "ImageId" not in kwargs:
            msg = "ImageId was not found in launch configuration. Cannot continue!"
            logger.error(msg)
            raise InvalidLaunchConfiguration(msg)
        
        # Create the vm id to pass into the other functions
        logger.debug("Generating vm-id")
        # Create our VirtualMachine Database object
        vm_db = VirtualMachine()
        # Generate the ID
        vm_db.generate_id()
        logger.info(f"Generated vm-id: {self.vm_db.instance_id}")
        self.user = user

        try:
            result = self._create_virtual_machine(vm_db, instanceType, **kwargs)
        except InvalidLaunchConfiguration as e:
            logger.error(f"Launch Configuration error: {e}")
            self._clean_up(user, self.vm_db.instance_id)
            raise
        except LaunchError as e:
            logger.exception(f"Launch error: {e}")
            self._clean_up(user, self.vm_db.instance_id)
            raise
        except Exception as e:
            logger.exception(f"Encountered other error: {e}")
            self._clean_up(user, self.vm_db.instance_id)
            raise
        finally:
            # Clean up after ourselves objects
            self._del_objects()
        
        return result


    def _create_virtual_machine(self, vm_db:VirtualMachine, instance_def:InstanceDefinition, **kwargs):
        """Actual method that creates a virtual machine."""
        logger.debug(kwargs)

        # Creating the directory for the virtual machine
        self.vm_dir = self.__generate_vm_path()
        vm_db.path = self.vm_dir

        # Create our new VirtualMachineInstance
        self.instance = VirtualMachineInstance()
        
        # Determine host to run this VM on:
        try:
            hosts = HostMachine.objects.all()
            # TODO: Allow setting the host (or picking one that fits)
        # When we can add multiple servers
            self.vm_db.host = hosts[0]
        except Exception as e:
            logger.exception(e)
            raise 
            
        # Prepare some variables
        private_ip:str  = kwargs["PrivateIp"] if "PrivateIp" in kwargs else None
        key_name:str    = kwargs["KeyName"] if "KeyName" in kwargs else None
        tags:dict       = kwargs["Tags"] if "Tags" in kwargs else {}
        enable_vnc:bool = True if "EnableVnc" in kwargs and kwargs["EnableVnc"] == "true" else False
        vnc_port:str    = kwargs["VncPort"] if "VncPort" in kwargs else None

        # Prepare our boot disk image and save the metadata to the DB
        self.vm_db.image_metadata = self.prepare_disk(kwargs["ImageId"])

        # initialize our CloudInit object
        self.cloudinit = CloudInit(base_dir=self.vm_dir)

        # Networking (May also set a cloudinit network config file)
        vnet_metadata = self.prepare_network_interface(kwargs["NetworkProfile"], private_ip)
        self.vm_db.interfaces = {
            "config_at_launch": vnet_metadata
        }

        # SSH keys (If configured)
        if key_name:
            public_key, key_dict = self.prepare_ssh_keys(key_name)
            self.vm_db.key_name = key_name

        # Generate the cloudinit Userdata
        # This includes the public keys and user data scripts if any exist.
        self.cloudinit.generate_userdata_config(
            vm_id = self.vm_db.instance_id,
            public_keys = [public_key],
            user_data_script = kwargs["UserDataScript"] if "UserDataScript" in kwargs else None
        )
        
        # Provides some generic information about our environment to the VM.
        self.cloudinit.generate_metadata(self.vm_db.instance_id, ip_addr=private_ip, public_key=key_dict)

        # Validate and create the cloudinit iso
        try:
            cloudinit_iso_path = self.cloudinit.create_iso()
        except CloudInitFailedValidation as e:
            logger.exception(e)
            raise VirtualMachineConfigurationError
        except CloudInitIsoCreationError as e:
            logger.exception(e)
            raise VirtualMachineConfigurationError
            
        if cloudinit_iso_path:
            self.instance.add_removable_media(cloudinit_iso_path, "hda")
    
        # VNC?
        metadata = {}
        if enable_vnc:
            metadata += self.configure_vnc(vnc_port)
            
        # Generate the virtual machine XML document and (try to) launch our VM!
        self.instance.configure_core(instance_def)
        self.instance.define()
        self.instance.start()

        # Add the information for this VM in the db
        self.vm_db.instance_type = instance_def.itype
        self.vm_db.instance_size = instance_def.isize
        self.vm_db.account = self.user.account
        self.vm_db.storage = {}
        self.vm_db.metadata = metadata
        self.vm_db.firewall_rules = {}
        self.vm_db.tags = tags
        self.vm_db.save()

        logger.debug(f"Successfully created VM: {self.vm_db.instance_id} : {self.vm_dir}")
        return self.vm_db.instance_id


    def configure_vnc(self, vnc_port:str = None) -> dict:
        """This will provide a VNC configuration if a user requests it"""
        logger.debug("Enabling VNC")

        # Generate a random password
        vnc_passwd = User().generate_secret(16)
        
        # Configure the instance
        self.instance.configure_vnc(vnc_port, vnc_passwd)

        # TODO: Store in Vault or a proper key store
        return {
            'vnc': {
                'password': str(base64.b64encode(bytes(vnc_passwd, 'utf-8')), 'utf-8')
            }
        }


    def get_image_from_id(self, image_id:str, user:User) -> BaseImageModel:
        """Returns an image object from an image_id string"""
        logger.debug("Determining image metadata..")
        
        # check if it's a user image
        image = None
        try:
            image:UserImage = UserImage.objects.get(
                account=user.account,
                image_id=image_id,
                deactivated=False
            )
            
        except UserImage.DoesNotExist:
            logger.debug(f"Did not find User defined image with ID: {image_id}")
        
        # Or a guest image
        try:
            image:GuestImage = GuestImage.objects.get(
                image_id=image_id,
                deactivated=False
            )
        except GuestImage.DoesNotExist:
            logger.debug(f"Did not find Guest defined image with ID: {image_id}")
        
        if not image:
            msg = "Provided ImageId does not exist."
            logger.error(msg)
            raise InvalidImageId(msg)
        
        return image
    

    def copy_image(self, image:BaseImageModel) -> str:
        """Copy a guest or user image to the path. Returns the full path of the copied image."""
        img_path = image.image_path
        img_format = image.format

        # Create a copy of the VM image
        destination_vm_img = f"{self.vm_dir}/{self.vm_db.instance_id}.{img_format}"
        try:
            logger.debug(f"Copying image: {img_path} TO directory {self.vm_dir} as {self.vm_db.instance_id}.{img_format}")
            shutil.copy2(img_path, destination_vm_img)
        except:
            raise LaunchError("Encountered an error on VM copy. Cannot continue.")

        logger.debug(f"Final image: {destination_vm_img}")
        return destination_vm_img


    def prepare_disk(self, image_id:str, disk_size:str = "10G") -> dict:
        """Given an image ID and disk size, will prepare a virtual disk for the VM."""
        # Get the image from the image id:
        logger.debug("Preparing disk..")
        try:
            image:BaseImageModel = self.get_image_from_id(image_id)
        except InvalidImageId:
            raise
        
        # Then copy our image to the destination directory
        image_iso_path = self.copy_image(image)

        new_vol = Volume(
            account=self.user.account,
            host=self.vm_db.host,
            virtual_machine=self.vm_db,
            parent_image=image.image_id,
            format=image.metadata["format"],
            path=image_iso_path
        )
        new_vol.generate_id()

        # resize our disk
        logger.debug(f"Resizing image size to {disk_size}")
        try:
            QemuImg().resize(image_iso_path, disk_size)
        except Exception as e:
            logger.error(f"Encountered error when running qemu resize. {e}")
            raise LaunchError("Encountered error when running qemu resize.")
        
        new_vol.populate_details()
        logger.debug(f"Created new volume: {new_vol.volume_id}")

        self.instance.add_virtual_disk(new_vol, "vda")

        return {
            "image_id": image_id,
            "image_name": image.name,
            "disk_size": disk_size,
            "volume_id": new_vol.volume_id
        }


    def prepare_network_interface(self, network_name:str, private_ip:str = None) -> dict:
        """Networking
        For VMs launched with BridgeToLan, we'll need to create a cloudinit
        network file as we're unable to set a private IP address at build time.
        It must instead be configured during boot with cloud-init.
        For all other VMs, we can omit the cloudinit ISOs and use the metadata
        API.
        """
        # Determine what network profile we're using:
        try:
            vnet = VirtualNetwork.objects.get(
                name=network_name,
                account=self.user.account
            )
        except VirtualNetwork.DoesNotExist:
            raise InvalidLaunchConfiguration("Provided NetworkProfile does not exist.")

        
        # Cloud-init for Bridge type networking
        if vnet.type == VirtualNetwork.Type.BRIDGE_TO_LAN:
            logger.debug("New virtual machine is using vnet type BridgeToLan")
            # If the IP is specified, check that the IP is valid for their network
            if private_ip and not VirtualNetworkManager().validate_ip(vnet, private_ip):
                raise InvalidLaunchConfiguration("Provided Private IP address is not valid for the specified network profile.")
            
            # Generate the Cloudinit Networking config
            logger.debug("CloudInit: Creating network config")
            self.cloudinit.generate_network_config(vnet, private_ip)

        self.instance.configure_network(vnet)

        return  {
            "vnet_id": vnet.network_id,
            "type": vnet.type,
            "private_ip": private_ip if private_ip else "",
        }


    def prepare_ssh_keys(self, key_name:str):
        """Adds SSH keys to the virtual machine"""
        logger.debug(f"Checking KeyName: {key_name}.")
        try:
            keyObj:UserKey = UserKey.objects.get(
                account=self.user.account,
                name=key_name
            )
            logger.debug("Got public key from KeyName")
            return keyObj.public_key,{key_name: [keyObj.public_key]}
        except UserKey.DoesNotExist:
            raise ValueError("Specified SSH Key Name does not exist.")

    
    def get_instance_configuration(self, vm_id):
        """Returns an object with the configuration details of a defined VM. (dump xml)"""
        domain = self.__get_libvirt_domain(vm_id)
        xmldoc = domain.XMLDesc()
        xmltodict.parse(xmldoc)
    

    def get_vm_db_from_id(self, vm_id:str):
        try:
            return VirtualMachine.objects.get(instance_id=vm_id)
        except VirtualMachine.DoesNotExist:
            raise VirtualMachineDoesNotExist


    def create_virtual_machine_image(self, vm_id:str, user:User, name:str, desc:str, tags:dict = {}):
        """Create a virtual machine image to create new virtual machines from"""
        account_id = user.account
        vm_name = f"{vm_id}.qcow2" # TODO: CHANGE THIS TO ACTUAL MACHINE IMAGE FILE

        vm_db = self.get_vm_db_from_id(vm_id)
        image_id = self.get_image_from_id(vm_db.image_metadata['image_id'], user)

        new_vmi = UserImage(
            account=user.account,
            name=name,
            description=desc,
            tags=tags,
            os=image_id.os,
        )
        new_vmi.generate_id()

        logger.debug(f"Creating VMI from {vm_id}")
        self.stop_instance(vm_id)

        user_vmi_dir = f"{VM_ROOT_DIR}/{account_id}/account_vmi"
        # Create it if doesn't exist
        pathlib.Path(user_vmi_dir).mkdir(parents=True, exist_ok=True)
        current_image_full_path = f"{VM_ROOT_DIR}/{account_id}/{vm_id}/{vm_name}"
        new_image_full_path = f"{user_vmi_dir}/{new_vmi.image_id}.qcow2"

        new_vmi.image_path=new_image_full_path
        new_vmi.save()

        # Copy the image to the new VM directory
        if not QemuImg().convert(current_image_full_path, new_image_full_path):
            raise ImagePrepError("Failed copying image with QemuImg() convert")

        # Prep the image for use in a new VM
        if not VirtTools().sysprep(new_image_full_path):
            raise ImagePrepError("Failed copying image with VirtTools() sysprep")

        # Resize the image
        if not VirtTools().sparsify(new_image_full_path):
            raise ImagePrepError("Failed copying image with VirtTools() sparsify")
        
        new_vmi.status = BaseImageModel.Status.READY
        new_vmi.save()

        return {"vmi_id": new_vmi.image_id}
        

    def try_get_database_object(self, vm_id:str, user:User):
        try:
            return VirtualMachine.objects.get(
                instance_id=vm_id,
                account=user.account
            )
        except VirtualMachine.DoesNotExist:
            raise


    def terminate_instance(self, vm_id:str, user:User, force:bool = False):
        """Terminate the instance"""
        logger.debug(f"Terminating vm: {vm_id}")
        if force:
            logger.warn("FORCE SET TO TRUE!")

        vm_db = self.try_get_database_object(vm_id, user)

        vm_domain = self.__get_libvirt_domain(vm_db.instance_id)

        # Stop the instance and undefine (remove) from Virsh
        self.stop_instance(vm_db.instance_id)
        self.__undefine_domain(vm_db.instance_id)
        
        # Delete folder/path
        self.__delete_vm_path(vm_db.instance_id, user)

        # delete entry in db
        try:
            if vm_db: 
                vm_db.delete()
        except Exception as e:
            raise Exception(f"Unable to delete row from database. instance_id={self.vm_db.instance_id}")

        return True


    def __get_libvirt_domain(self, vm_id:str):
        """Returns currentConnection object if the VM exists. Returns False if vm does not exist."""
        try:
            return self.currentConnection.lookupByName(vm_id)
        except libvirt.libvirtError as e:
            # Error code 42 = Domain not found
            if (e.get_error_code() == libvirt.VIR_ERR_NO_DOMAIN):
                return False


    def __generate_vm_path(self):
        """Create a path for the virtual machine files to be created in"""
        vm_path = f"{VM_ROOT_DIR}/{self.user.account}/{self.vm_db.instance_id}"
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
        if vm_id is None or vm_id.strip() == "":
            logger.warning("vm_id empty when calling delete_vm_path. Exiting!")
            return

        path = f"{VM_ROOT_DIR}/{user.account}/{vm_id}"
        logger.debug(f"Deleting VM Path: {path}")

        try:
            shutil.rmtree(path)
        except:
            logger.error("Encountered an error when atempting to delete VM path.")


    def __undefine_domain(self, vm_id:str):
        vm = self.__get_libvirt_domain(vm_id)
        if vm:
            vm.undefine()


    def _del_objects(self):
        logger.debug("Deleting objects")
        del self.cloudinit
        del self.vm_db
        del self.instance


    def __run_command(self, cmd: list, env: dict = {}):
        logger.debug("Running command: ")
        logger.debug(cmd)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True, env=env)
        logger.debug("Waiting..")
        process.wait()
        logger.debug("Process Wait finished")
        output = process.stdout.readline()
        logger.debug(output.strip())
        return_code = process.poll()
        logging.debug(f"SUBPROCESS RETURN CODE: {return_code}")
        return {
            "return_code": return_code,
            "output": output,
        }

    