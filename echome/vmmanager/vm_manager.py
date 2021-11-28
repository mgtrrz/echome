import logging
import shutil
import base64
import os
from pathlib import Path
from echome.config import ecHomeConfig
from commander.qemuimg import QemuImg
from commander.virt_tools import VirtTools
from identity.models import User
from network.models import VirtualNetwork
from network.manager import VirtualNetworkManager
from keys.models import UserKey
from .image_manager import ImageManager
from .models import VirtualMachine, HostMachine, Volume, Image
from .instance_definitions import InstanceDefinition
from .cloudinit import CloudInit, CloudInitFailedValidation, CloudInitIsoCreationError
from .vm_instance import VirtualMachineInstance
from .exceptions import (
    LaunchError, 
    InvalidLaunchConfiguration, 
    VirtualMachineDoesNotExist, 
    VirtualMachineConfigurationError, 
    ImagePrepError,
    ImageDoesNotExistError
)

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

    cloudinit:CloudInit = None
    vm_db:VirtualMachine = None
    instance:VirtualMachineInstance = None

    def create_vm(self, user: User, instance_def:InstanceDefinition, **kwargs):
        """Create a virtual machine
        This function does not create the VM but instead passes all of the arguments to the internal
        function _create_virtual_machine(). If this process fails, the function will clean up after
        itself. Set the environment var VM_CLEAN_UP_ON_FAIL to False to alter this behavior to keep
        files for debugging purposes.

        Args:
            user (User): User object for identifying which account the VM is created for.
            instance_def (InstanceDefinition): Instance type for the virtual machine to use.
        
        Kwargs:
            NetworkProfile (str): Network profile to use for the virtual machine. Use the name rather than the ID.
            ImageId (str): Guest or User image ID to spawn the virtual machine from.
            DiskSize (str): Disk size for the virtual machine. (e.g. 10G, 200G, 10000M). Defaults to 10G.
            KeyName (str, optional): Name of the SSH Keystore item to add a public ssh key to the VM.
            PrivateIp (str, optional): Private IP address to assign.
            UserDataScript (str, optional): User-data shell script to boot the instance with.
            Tags (dict, optional): Dictionary of tags to apply to this instance.
            EnableVnc (bool, optional): Whether this machine will have VNC enabled.
            VncPort (str, optional): Value for the VNC port (if enabled above).
            Files (List[CloudInitFile], optional): Files to upload to the virtual machine
            RunCommands (List[str], optional): List of commands to run

        Raises:
            InvalidLaunchConfiguration: If supplied arguments are invalid for this virtual machine.
            LaunchError: If there was an error during build of the virtual machine.

        Returns:
            dict: [description]
        """


        # We need an image id to create our VM!
        if "ImageId" not in kwargs:
            msg = "ImageId was not found in launch configuration. Cannot continue!"
            logger.error(msg)
            raise InvalidLaunchConfiguration(msg)
        
        self.user = user

        # Create our VirtualMachine Database object
        instance_id = self.prepare_vm_db(user, instance_def, kwargs["Tags"] if "Tags" in kwargs else {})

        # Creating the directory for the virtual machine
        self.vm_dir = self.__generate_vm_path(user.account, instance_id)
        self.vm_db.path = self.vm_dir
        
        try:
            result = self._create_virtual_machine(instance_def, **kwargs)
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


    def _create_virtual_machine(self, instance_def:InstanceDefinition, **kwargs):
        """Actual method that creates a virtual machine."""
        logger.debug(kwargs)

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
        enable_vnc:bool = True if "EnableVnc" in kwargs and kwargs["EnableVnc"] == "true" else False
        vnc_port:str    = kwargs["VncPort"] if "VncPort" in kwargs else None

        # Prepare our boot disk image and save the metadata to the DB
        self.vm_db.image_metadata = self.prepare_disk(kwargs["ImageId"], kwargs["DiskSize"])

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
            public_keys = [public_key],
            user_data_script = kwargs["UserDataScript"] if "UserDataScript" in kwargs else None,
            files = kwargs["Files"] if "Files" in kwargs else None,
            run_command = kwargs["RunCommands"] if "RunCommands" in kwargs else None
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
        self.instance.define(self.vm_db)
        self.instance.start()

        # Add the information for this VM in the db
        self.vm_db.storage = {}
        self.vm_db.metadata = metadata
        self.finish_vm_db()

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


    def prepare_disk(self, image_id:str, disk_size:str = "10G") -> dict:
        """Given an image ID and disk size, will prepare a virtual disk for the VM."""
        # Get the image from the image id:
        logger.debug("Preparing disk..")
        img_mgr = ImageManager()
        try:
            image:Image = img_mgr.get_image_from_id(image_id, self.user)
        except ImageDoesNotExistError:
            raise
        
        # Copy our image to the destination directory
        image_iso_path = img_mgr.copy_image(image, Path(self.vm_dir), self.vm_db.instance_id)

        new_vol = Volume(
            account=self.user.account,
            host=self.vm_db.host,
            virtual_machine=self.vm_db,
            path=image_iso_path,
        )
        new_vol.generate_id()
        new_vol.new_volume_from_image(image)
        new_vol.save()

        # resize our disk
        logger.debug(f"Resizing image size to {disk_size}")
        try:
            QemuImg().resize(image_iso_path, disk_size)
        except Exception as e:
            logger.error(f"Encountered error when running qemu resize. {e}")
            raise LaunchError("Encountered error when running qemu resize.")
        
        new_vol.populate_metadata()
        logger.debug(f"Created new volume: {new_vol.volume_id}")

        self.instance.add_virtual_disk(new_vol, "vda")
        new_vol.state = Volume.State.ATTACHED
        new_vol.save()

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


    def get_vm_db_from_id(self, vm_id:str):
        try:
            return VirtualMachine.objects.get(instance_id=vm_id)
        except VirtualMachine.DoesNotExist:
            raise VirtualMachineDoesNotExist


    def create_virtual_machine_image(self, 
            vm_id:str, user:User, name:str = None, description:str = None, 
            tags:dict = None, prepared_manager:ImageManager = None):
        """Create a virtual machine image to create new virtual machines from."""

        logger.debug(f"Creating VMI from {vm_id}")

        if not prepared_manager:
            image_manager = ImageManager()
            new_vmi_id = image_manager.prepare_user_image(user, name, description, tags)
            logger.debug(f"New VMI ID: {new_vmi_id}")
        else: 
            image_manager = prepared_manager
            new_vmi_id = image_manager.image.image_id


        # Stop the instance (we can't copy a live machine, yet)
        instance = VirtualMachineInstance(vm_id)
        # But first, get the current state so we can start it back up if it was on before.
        before_state, _, _ = instance.get_vm_state()
        logger.debug(f"Previous VM state: {before_state}")
        instance.stop()

        # Define the path to the account vmi directory & create it if doesn't exist
        user_vmi_dir = self.__return_account_user_images_path(user.account)
        logger.debug(f"User_vmi_dir: {user_vmi_dir}")

        current_image_full_path = self.__return_vm_path(user.account, vm_id) / f"{vm_id}.qcow2"
        logger.debug(f"Current image full path: {current_image_full_path}")
        new_image_full_path = user_vmi_dir / f"{new_vmi_id}.qcow2"
        logger.debug(f"New image full path: {new_image_full_path}")

        # Copy the image to the new VM directory
        if not QemuImg().convert(current_image_full_path, new_image_full_path, 'qcow2'):
            raise ImagePrepError("Failed copying image with QemuImg() convert")

        # Revert the state of the VM (if it was running, turn it back on)
        if before_state == "running":
            instance.start()

        # Prep the image for use in a new VM
        if not VirtTools().sysprep(new_image_full_path):
            raise ImagePrepError("Failed copying image with VirtTools() sysprep")

        # Resize the image
        if not VirtTools().sparsify(new_image_full_path):
            raise ImagePrepError("Failed copying image with VirtTools() sparsify")
        
        image_manager.finish_user_image(new_image_full_path)

        return {"vmi_id": new_vmi_id}
        

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

        instance = VirtualMachineInstance(vm_id)
        # Stop the instance and undefine (remove) from Virsh
        instance.stop()
        instance.terminate()
        
        # Delete folder/path
        self.__delete_vm_path(vm_db.instance_id, user)

        # Delete the volume from the database
        Volume.objects.filter(virtual_machine=vm_db).delete()

        # delete entry in db
        if vm_db: 
            vm_db.delete()

        return True
    

    def prepare_vm_db(self, user:User, instance_def:InstanceDefinition, tags:dict = {}) -> str:
        """Prepare the virtual machine Database object. Use finish_vm_db() to finalize the DB details."""
        vm_db = VirtualMachine(
            account=user.account,
            tags=tags,
        )
        vm_db.set_instance_definition(instance_def)
        vm_db.generate_id()

        logger.info(f"Generated vm-id: {vm_db.instance_id}")
        self.vm_db = vm_db
        self.vm_db.save()

        return vm_db.instance_id

    
    def finish_vm_db(self):
        if not self.vm_db:
            raise VirtualMachineConfigurationError("No vm_db object to finish db with.")
        
        self.vm_db.state = VirtualMachine.State.AVAILABLE
        self.vm_db.save()
        

    def __return_account_user_images_path(self, user_account:str) -> Path:
        try:
            vm_path = Path(f"{VM_ROOT_DIR}/{user_account}/account_vmi")
            vm_path.mkdir(parents=True, exist_ok=True)
            return vm_path
        except Exception:
            logger.error("Encountered an error when attempting to return VMI path. Cannot continue.")
            raise
    

    def __return_vm_path(self, user_account:str, instance_id:str):
        return Path(f"{VM_ROOT_DIR}/{user_account}/{instance_id}")


    def __generate_vm_path(self, user_account:str, instance_id:str):
        """Create a path for the virtual machine files to be created in"""
        vm_path = f"{VM_ROOT_DIR}/{user_account}/{instance_id}"
        logger.debug(f"Generated VM Path: {vm_path}. Creating..")
        try:
            Path(vm_path).mkdir(parents=True, exist_ok=False)
            logger.info(f"Created VM Path: {vm_path}")
            return vm_path
        except Exception:
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


    def _clean_up(self, user:User, vm_id:str):
        """Cleans up a virtual machine directory if CLEAN_UP_ON_FAIL is true
        This should only be run when the virtual machine creation process fails!
        """
        if CLEAN_UP_ON_FAIL:
            logging.debug("CLEAN_UP_ON_FAIL set to true. Cleaning up..")
            self.vm_db.delete()
            self.__delete_vm_path(vm_id, user)

        if self.instance:
            self._del_disks(self.instance)
            del self.instance


    def _del_objects(self):
        """Clean up objects for memory management"""
        logger.debug("Deleting objects")
        if self.cloudinit:
            logger.debug("Deleting self.cloudinit")
            del self.cloudinit

        if self.vm_db:
            logger.debug("Deleting self.vm_db")
            del self.vm_db

        if self.instance:
            logger.debug("Deleting self.instance")
            del self.instance


    def _del_disks(self, instance:VirtualMachineInstance):
        """Deletes orphan disks that were created during the creation process."""
        logger.debug("Deleting any orphan disks")
        if not instance.virtual_disks:
            logger.debug("None to delete")
            return
        
        for disk in instance.virtual_disks.values():
            try:
                logger.debug(f"Found disk with alias: {disk.alias}")
                Volume.objects.filter(volume_id=disk.alias).delete()
            except Volume.DoesNotExist:
                pass

    