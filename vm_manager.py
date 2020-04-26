import libvirt
from string import Template
import uuid
import pathlib
import logging
import subprocess
from instance_definitions import Instance

VM_ROOT_DIR = "/data/ssd_storage/user_instances"

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

    def createInstance(self, instanceType:Instance, cloudinit_params):
        
        # If we have Cloud-init config, build and test it

        # cloudInitConfig = {
        #     "path": "/test/just/testing"
        # }

        logging.debug("Generating vm-id")
        vm_id = self.__generate_vm_id()
        logging.debug(f"Generated vm-id: {vm_id}")

        # Generating the tmp path for creating/copying/validating files
        tmpdir = self.__generate_tmp_path("12345", vm_id)
        logging.debug(f"Temp logging directory: {tmpdir}")


        # Generate cloudinit config
        cloudinit_params["vm_id"] = vm_id
        standard_cloudinit_config = self.__generate_cloudinit_config(cloudinit_params)
        # Create the Cloudinit yaml in tmp dir
        cloudinit_yaml_file_path = f"{tmpdir}/cloudinit.yaml"

        with open(cloudinit_yaml_file_path, "w") as filehandle:
            logging.debug("Writing cloudinit yaml: cloudinit.yaml")
            filehandle.write(standard_cloudinit_config)
        # TODO: Catch errors 

        # Validate and create the cloudinit iso
        cloudinit_iso_path = self.__create_cloudinit_iso(tmpdir)

        # Generate VM
        vm_config = {
            "vm_id": vm_id,
            "cpu": instanceType.get_cpu(),
            "memory": instanceType.get_memory(),
            "xml_template": instanceType.get_xml_template(),
            "cloud_init_path": cloudinit_iso_path,
        }
        xmldoc = self.__generate_new_vm_template(vm_config)

        # Create the actual files in the tmp dir
        with open(f"{tmpdir}/vm.xml", 'w') as filehandle:
            logging.debug("Writing virtual machine doc: vm.xml")
            filehandle.write(xmldoc)

        print(xmldoc)
        print(standard_cloudinit_config)
    

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
                'CLOUDINIT_DISK': cloudinit_xml
            }
        
        return src.substitute(replace)
    
    def __generate_cloudinit_config(self, config):
        # If hostname is not supplied, use the instance ID
        if "hostname" not in config or config["hostname"] == "":
            config["hostname"] = config["vm_id"]

        cloud_init = """#cloud-config
chpasswd: {{ expire: False }}
ssh_pwauth: False
hostname: {}
ssh_authorized_keys:
  - {}
        """.format(config["hostname"], config["cloudinit_key"])
        return cloud_init
    

    def __create_cloudinit_iso(self, tmpdir):

        cloudinit_yaml_file_path = f"{tmpdir}/cloudinit.yaml"

        # Validate the yaml file
        process = subprocess.Popen(['cloud-init', 'devel', 'schema', '--config-file', cloudinit_yaml_file_path], 
                           stdout=subprocess.PIPE,
                           universal_newlines=True)
        output = process.stdout.readline()
        print(output.strip())
        # Do something else
        return_code = process.poll()
        print(return_code)
        if return_code is not None:
            print('RETURN CODE', return_code)
            # There was an issue with the cloud init file
            #TODO: Condition on error
            # Process has finished, read rest of the output 
            for output in process.stdout.readlines():
                print(output.strip())

        #TODO: Network config file

        # Create cloud_init disk image
        cloudinit_iso_path = f"{tmpdir}/cloudinit.iso"
        process = subprocess.Popen(['cloud-localds', '-v', cloudinit_iso_path, cloudinit_yaml_file_path], 
                           stdout=subprocess.PIPE,
                           universal_newlines=True)
        output = process.stdout.readline()
        print(output.strip())
        # Do something else
        return_code = process.poll()
        print(return_code)
        if return_code is not None:
            print('RETURN CODE', return_code)
            # There was an issue with the cloud init file
            #TODO: Condition on error
            # Process has finished, read rest of the output 
            for output in process.stdout.readlines():
                print(output.strip())
        
        return cloudinit_iso_path

    def __generate_vm_id(self):
        return "vm-" + str(uuid.uuid1()).replace("-", "")[0:8]

    def __generate_tmp_path(self, account_id, vm_id):
        tmp_path = f"{VM_ROOT_DIR}/{account_id}/tmp/{vm_id}"
        pathlib.Path(tmp_path).mkdir(parents=True, exist_ok=True)
        return tmp_path


    def __delete_tmp_path(self, account_id, vm_id):
        tmp_path = f"{VM_ROOT_DIR}/{account_id}/tmp/{vm_id}"
