import libvirt
from string import Template
import uuid
import pathlib
import logging
import subprocess
import random
import shutil
import time
from instance_definitions import Instance

VM_ROOT_DIR = "/data/ssd_storage/user_instances"
VM_GUEST_IMGS = "/data/ssd_storage/guest_images"

CLEAN_UP_ON_FAIL = True

# Flow for VM Creation
# 1. Generate a VM Id
# 2. Generate the cloudinit config
#   a. Save the cloudinit config to a temporary folder
#   b. validate the file
#   c. create an disk img for the cloudinit file
# 3. Generate the VM XML document
# 4. Launch new VM with XML document

class vmManager:

    def __init__(self):
        self.currentConnection = libvirt.open('qemu:///system')

    def getConnection(self):
        return self.currentConnection

    def closeConnection(self):
        self.currentConnection.close()

    def createInstance(self, instanceType:Instance, cloudinit_params, server_params):

        account_id = "12345"

        logging.debug("Generating vm-id")
        vm_id = self.__generate_vm_id()
        logging.debug(f"Generated vm-id: {vm_id}")

        # Generating the tmp path for creating/copying/validating files
        vmdir = self.__generate_vm_path(account_id, vm_id)
        logging.debug(f"Create VM directory: {vmdir}")


        # Generate cloudinit config
        cloudinit_params["vm_id"] = vm_id
        standard_cloudinit_config = self.__generate_cloudinit_config(cloudinit_params)
        # Create the Cloudinit yaml in tmp dir
        cloudinit_yaml_file_path = f"{vmdir}/cloudinit.yaml"

        with open(cloudinit_yaml_file_path, "w") as filehandle:
            logging.debug("Writing cloudinit yaml: cloudinit.yaml")
            filehandle.write(standard_cloudinit_config)
        # TODO: Catch errors 

        # If we set a static IP for the instance, create a network config file
        network_yaml_file_path = ""
        if "private_ip" in cloudinit_params:
            network_cloudinit_config = self.__generate_network_cloudinit_config(cloudinit_params)
            network_yaml_file_path = f"{vmdir}/network.yaml"

            with open(network_yaml_file_path, "w") as filehandle:
                logging.debug("Writing cloudinit yaml: network.yaml")
                filehandle.write(network_cloudinit_config)
            # TODO: Catch errors 

        # Validate and create the cloudinit iso
        cloudinit_iso_path = self.__create_cloudinit_iso(vmdir, cloudinit_yaml_file_path, network_yaml_file_path)

        # Is this a guest image or a user-created virtual machine image?
        if "image" in server_params:
            img_type = "base guest image"
            img_name = server_params['image']
            image_base_dir = f"{VM_GUEST_IMGS}"
        else:
            img_type = "user virtual machine image"
            img_name = server_params["vmi"]
            image_base_dir = f"{VM_ROOT_DIR}/{account_id}/user_vmi"

        # Create a copy of the VM image
        try:
            logging.debug(f"Copying {img_type}: {image_base_dir}/{img_name} TO {vmdir}")
            shutil.copy2(f"{image_base_dir}/{img_name}", vmdir)
        except:
            logging.error("Encountered an error on VM copy. Cannot continue.")
            if CLEAN_UP_ON_FAIL:
                self.__delete_vm_path(account_id, vm_id)
            raise

        vm_img = f"{vmdir}/{img_name}"
        logging.debug(f"Final image: {vm_img}")


        # Generate VM
        logging.debug(f"Generating vm config")
        vm_config = {
            "vm_id": vm_id,
            "cpu": instanceType.get_cpu(),
            "memory": instanceType.get_memory(),
            "xml_template": instanceType.get_xml_template(),
            "cloud_init_path": cloudinit_iso_path,
            "vm_img": vm_img
        }
        logging.debug(vm_config)
        xmldoc = self.__generate_new_vm_template(vm_config)

        # Create the actual files in the tmp dir
        with open(f"{vmdir}/vm.xml", 'w') as filehandle:
            logging.debug("Writing virtual machine doc: vm.xml")
            filehandle.write(xmldoc)

        logging.debug(xmldoc)
        logging.debug(standard_cloudinit_config)

        logging.debug(f"Resizing image size to {server_params['disk_size']}")
        output = self.__run_command(['qemu-img', 'resize', vm_img, server_params["disk_size"]])
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")

        
        logging.debug("Attempting to define XML with virsh..")
        self.currentConnection.defineXML(xmldoc)
        logging.info("Starting VM..")
        self.startInstance(vm_id)

        print(f"Successfully created VM: {vm_id} : {vmdir}")
        return {
            "success": True,
            "meta_data": {
                "vm_id": vm_id
            },
            "reason": "",
        }

    def createVirtualMachineImage(self, vm_id):
        # Instance needs to be turned off to create an image
        self.stopInstance(vm_id)



    def startInstance(self, vm_id):
        vm = self.__get_vm_connection(vm_id)
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
        vm = self.__get_vm_connection(vm_id)
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

    # Terminate the instance 
    def terminateInstance(self, vm_id):
        logging.debug(f"Terminating vm: {vm_id}")

        vm = self.__get_vm_connection(vm_id)
        if not vm:
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
            print(f"Successfully terminated instance {vm_id}")
            return {
                "success": True,
                "meta_data": {},
                "reason": "",
            }
        except libvirt.libvirtError as e:
            logging.error(f"Could not terminate instance {vm_id}: libvirtError {e}")
            return {
                "success": False,
                "meta_data": {},
                "reason": f"Could not terminate instance {vm_id}: libvirtError {e}",
            }

    # Returns currentConnection object if the VM exists. Returns False if vm does not exist.
    def __get_vm_connection(self, vm_id):
        try:
            return self.currentConnection.lookupByName(vm_id)
        except libvirt.libvirtError as e:
            # Error code 42 = Domain not found
            if (e.get_error_code() == 42):
                return False

    # Generate XML template for virt to create the image with
    def __generate_new_vm_template(self, config):
        cloudinit_xml = ""
        
        # Generate disk XML
        if config["cloud_init_path"]:
            with open(f"./xml_templates/cloudinit_disk.xml", 'r') as filehandle:
                cloudinit_xml = Template(filehandle.read())
                replace = {
                    'VM_USER_CLOUDINIT_IMG_PATH': config["cloud_init_path"]
                }
                cloudinit_xml = cloudinit_xml.substitute(replace)

        # Generate the rest of the vm XML
        with open(f"./xml_templates/{config['xml_template']}", 'r') as filehandle:
            src = Template(filehandle.read())
            replace = {
                'VM_NAME': config["vm_id"],
                'VM_CPU_COUNT': config["cpu"], 
                'VM_MEMORY': config["memory"],
                'CLOUDINIT_DISK': cloudinit_xml,
                'VM_USER_IMG_PATH': config["vm_img"]
            }
        
        return src.substitute(replace)
    
    # Generate cloudinit yaml string
    def __generate_cloudinit_config(self, config):
        # If hostname is not supplied, use the instance ID
        if "hostname" not in config or config["hostname"] == "":
            config["hostname"] = config["vm_id"]

        cloud_init = """#cloud-config
chpasswd: {{ expire: False }}
ssh_pwauth: True
hostname: {}
ssh_authorized_keys:
  - {}
        """.format(config["hostname"], config["cloudinit_key"])
        return cloud_init


    # Generate network config for cloudinit yaml string
    def __generate_network_cloudinit_config(self, config):
        cloud_network_init = f"""version: 2
ethernets:
    ens2:
        dhcp4: false
        dhcp6: false
        addresses:
          - {config['private_ip']}
        gateway4: {config['gateway_ip']}
        nameservers:
          addresses:
            - 1.1.1.1
            - 1.0.0.1
        """

        return cloud_network_init
    
    # Generate an ISO from the cloudinit YAML files
    def __create_cloudinit_iso(self, vmdir, cloudinit_yaml_file_path, cloudinit_network_yaml_file_path=""):

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

        if cloudinit_network_yaml_file_path:
            args.append(f"--network-config={cloudinit_network_yaml_file_path}")

        output = self.__run_command(args)
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")

        logging.debug(f"Created cloudinit iso: {cloudinit_iso_path}")

        return cloudinit_iso_path

    # Generate a unique ID.
    def __generate_vm_id(self, type="vm", length=""):
        # Use default length unless length is manually specified
        default_vm_length = 8
        default_vmi_length = 8

        if type == "vm":
            prefix = "vm-"
            len = default_vm_length if length == "" else length 
        elif type  == "vmi":
            prefix = "vmi-"
            len = default_vmi_length if length == "" else length 

        uid = str(uuid.uuid1()).replace("-", "")[0:len]
        return f"{prefix}{uid}"

    def __generate_mac_addr(self):
        mac = [ 0x00, 0x16, 0x3e,
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0xff),
            random.randint(0x00, 0xff) ]
        return ':'.join(map(lambda x: "%02x" % x, mac))

    # Create a path for the files to be created in
    def __generate_vm_path(self, account_id, vm_id):
        vm_path = f"{VM_ROOT_DIR}/{account_id}/{vm_id}"
        try:
            pathlib.Path(vm_path).mkdir(parents=True, exist_ok=False)
            return vm_path
        except:
            logging.error("Encountered an error when attempting to generate VM path. Cannot continue.")
            raise

    # Delete the path for the files
    def __delete_vm_path(self, account_id, vm_id):
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