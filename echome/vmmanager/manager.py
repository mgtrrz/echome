import libvirt
import pathlib
import logging
import subprocess
import shutil
import time
import xmltodict
import base64
import os
from typing import List
from echome.id_gen import IdGenerator
from echome.config import ecHomeConfig
from commander.qemuimg import QemuImg
from identity.models import User
from images.models import BaseImageModel, GuestImage, UserImage, InvalidImageId
from network.models import VirtualNetwork
from network.manager import VirtualNetworkManager
from keys.models import UserKey
from .models import VirtualMachine, HostMachine
from .instance_definitions import InstanceDefinition
from .cloudinit import CloudInit, CloudInitFailedValidation, CloudInitIsoCreationError
from .xml_generator import KvmXmlObject, KvmXmlNetworkInterface, KvmXmlDisk, KvmXmlRemovableMedia, KvmXmlVncConfiguration, VirtualMachineXmlObject
from .exceptions import LaunchError, InvalidLaunchConfiguration, VirtualMachineDoesNotExist, VirtualMachineConfigurationException, VirtualMachineTerminationException

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

        # We need an image id to create our VM!
        if "ImageId" not in kwargs:
            msg = "ImageId was not found in launch configuration. Cannot continue!"
            logger.error(msg)
            raise InvalidLaunchConfiguration(msg)
        
        # Create the vm id to pass into the other functions
        logger.debug("Generating vm-id")
        # Create our VirtualMachine Database object
        self.vm_db = VirtualMachine()
        # Generate the ID
        self.vm_db.generate_id()
        logger.info(f"Generated vm-id: {self.vm_db.instance_id}")
        self.user = user

        try:
            result = self._create_virtual_machine(instanceType, **kwargs)
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
            raise
        
        return result


    def _create_virtual_machine(self, instanceType:InstanceDefinition, **kwargs):
        """Actual method that creates a virtual machine."""
        logger.debug(kwargs)

        # Creating the directory for the virtual machine
        self.vm_dir = self.__generate_vm_path()
        # this object houses all of the XML documents needed to define our virtual machine
        self.vm_xml_object = VirtualMachineXmlObject()
        
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
        except CloudInitFailedValidation:
            raise
        except CloudInitIsoCreationError:
            raise
            
        if cloudinit_iso_path:
            self.vm_xml_object.removable_media_xml_def.append(KvmXmlRemovableMedia(cloudinit_iso_path))
    
        # VNC?
        metadata = {}
        if enable_vnc:
            metadata += self.configure_vnc(kwargs["VncPort"] if "VncPort" in kwargs else None)
            
        # Generate the virtual machine XML document and (try to) launch our VM!
        self.define_virtual_machine(instanceType)

        # Add the information for this VM in the db
        self.vm_db.instance_type = instanceType.itype
        self.vm_db.instance_size = instanceType.isize
        self.vm_db.account = self.user.account
        self.vm_db.storage = {}
        self.vm_db.metadata = metadata
        self.vm_db.firewall_rules = {}
        self.vm_db.tags = tags
        
        try:
            self.vm_db.save()
        except Exception as e:
            logger.debug(e)
            raise Exception

        logger.debug(f"Successfully created VM: {self.vm_db.instance_id} : {self.vm_dir}")
        del self.vm_xml_object
        return self.vm_db.instance_id


    def configure_vnc(self, vnc_port:str = None) -> dict:
        """This will provide a VNC configuration if a user requests it"""
        logger.debug("Enabling VNC")
        vnc_xml_def = KvmXmlVncConfiguration(True)

        if vnc_port:
            logger.debug(f"VNC Port also specified: {vnc_port}")
            vnc_xml_def.vnc_port = vnc_port

        # Generate a random password
        vnc_passwd = User().generate_secret(16)
        vnc_xml_def.vnc_password = vnc_passwd

        # TODO: Store in Vault or a proper key store
        metadata = {
            'vnc': {
                'password': str(base64.b64encode(bytes(vnc_passwd, 'utf-8')), 'utf-8')
            }
        }
        self.vm_xml_object.vnc_xml_def = vnc_xml_def
        return metadata


    def get_image_from_id(self, image_id:str) -> BaseImageModel:
        """Returns an image object from an image_id string"""
        logger.debug("Determining image metadata..")
        
        # check if it's a user image
        image = None
        try:
            image:UserImage = UserImage.objects.get(
                account=self.user.account,
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
            image = self.get_image_from_id(image_id)
        except InvalidLaunchConfiguration:
            raise
        
        # Then copy our image to the destination directory
        image_iso_path = self.copy_image(image)

        # resize our disk
        logger.debug(f"Resizing image size to {disk_size}")
        try:
            QemuImg().resize(image_iso_path, disk_size)
        except Exception as e:
            logger.error(f"Encountered error when running qemu resize. {e}")
            raise LaunchError("Encountered error when running qemu resize.")
        
        self.vm_xml_object.virtual_disk_xml_def.append(KvmXmlDisk(
            file_path=image_iso_path,
            type=image.format,
            os_type=BaseImageModel.OperatingSystem(image.os).label
        ))

        return {
            "image_id": image_id,
            "image_name": image.name,
            "disk_size": disk_size
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

        xml_network_def = None
        
        # Cloud-init for Bridge type networking
        if vnet.type == VirtualNetwork.Type.BRIDGE_TO_LAN:
            logger.debug("New virtual machine is using vnet type BridgeToLan")
            # If the IP is specified, check that the IP is valid for their network
            if private_ip and not VirtualNetworkManager().validate_ip(vnet, private_ip):
                raise InvalidLaunchConfiguration("Provided Private IP address is not valid for the specified network profile.")
            
            # Generate the Cloudinit Networking config
            logger.debug("CloudInit: Creating network config")
            self.cloudinit.generate_network_config(vnet, private_ip)

            xml_network_def = KvmXmlNetworkInterface(
                type = "bridge",
                source = vnet.config['bridge_interface']
            )
        elif vnet.type == VirtualNetwork.Type.NAT:
            logger.debug("New virtual machine is using vnet type NAT")
            xml_network_def = KvmXmlNetworkInterface(
                type = "nat",
                source = vnet.name
            )
        
        self.vm_xml_object.virtual_network_xml_def = xml_network_def
        return {
            "config_at_launch": {
                "vnet_id": vnet.network_id,
                "type": vnet.type,
                "private_ip": private_ip if private_ip else "",
            }
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
        


    def define_virtual_machine(self, instance_type:InstanceDefinition):
        """Defines the virtual machine within virsh by generating an XML document and applying it"""
        logger.debug(f"Generating VM config")

        xmldoc = KvmXmlObject(
            name=self.vm_db.instance_id,
            memory=instance_type.get_memory(),
            cpu_count=instance_type.get_cpu(),
            network_interfaces=[self.vm_xml_object.virtual_network_xml_def],
            hard_disks=self.vm_xml_object.virtual_disk_xml_def
        )

        if self.vm_xml_object.removable_media_xml_def:
            xmldoc.removable_media = self.vm_xml_object.removable_media_xml_def

        # VNC
        if self.vm_xml_object.vnc_xml_def:
            xmldoc.vnc_configuration = self.vm_xml_object.vnc_xml_def
        
        xmldoc.enable_smbios = False
        xmldoc.smbios_url = ""

        # Render the XML doc        
        doc = xmldoc.render_xml()

        # Create the actual XML template in the vm directory
        # We don't need to save the XML document to the file system
        # as it gets saved within libvirt itself, but this is a good
        # way to debug templates generated by our script.
        with open(f"{self.vm_dir}/vm.xml", 'w') as filehandle:
            logger.debug("Writing virtual machine XML document: vm.xml")
            filehandle.write(doc)

        logger.debug("Attempting to define XML with virsh..")
        self.currentConnection.defineXML(doc)
        
        logger.info("Starting VM..")
        self.start_instance(self.vm_db.instance_id)
    
    
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

        user_vmi_dir = f"{VM_ROOT_DIR}/{account_id}/account_vmi"
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


    def get_vm_state(self, vm_id:str = None):
        """Get the state of the virtual machine as defined in libvirt."""
        vm_id = vm_id if vm_id else self.vm_db.instance_id
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

        
    def start_instance(self, vm_id:str = None):
        """Start an instance (and set autostart to 1 for host reboots)"""

        vm_id = vm_id if vm_id else self.vm_db.instance_id

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
    

    def stop_instance(self, vm_id:str = None):
        """Stop an instance"""

        vm_id = vm_id if vm_id else self.vm_db.instance_id

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
            if (e.get_error_code() == 42):
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
