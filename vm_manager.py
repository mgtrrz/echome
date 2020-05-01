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

        # Create a copy of the VM image
        shutil.copy2(f"{VM_GUEST_IMGS}/{server_params['image']}", vmdir)
        vm_img = f"{vmdir}/{server_params['image']}"

        # Generate VM
        vm_config = {
            "vm_id": vm_id,
            "cpu": instanceType.get_cpu(),
            "memory": instanceType.get_memory(),
            "xml_template": instanceType.get_xml_template(),
            "cloud_init_path": cloudinit_iso_path,
            "vm_img": vm_img
        }
        xmldoc = self.__generate_new_vm_template(vm_config)

        # Create the actual files in the tmp dir
        with open(f"{vmdir}/vm.xml", 'w') as filehandle:
            logging.debug("Writing virtual machine doc: vm.xml")
            filehandle.write(xmldoc)

        print(xmldoc)
        print(standard_cloudinit_config)

        process = subprocess.Popen(['qemu-img', 'resize', vm_img, server_params["disk_size"]], 
                           stdout=subprocess.PIPE,
                           universal_newlines=True)
        output = process.stdout.readline()
        print(output.strip())
        return_code = process.poll()
        logging.debug(f"SUBPROCESS RETURN CODE: {return_code}")
        if return_code is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            # Process has finished, read rest of the output 
            for output in process.stdout.readlines():
                print(output.strip())
        
        print(f"Successfully created VM: {vm_id} : {vmdir}")
        
        logging.debug("Attempting to define XML with virsh..")
        self.currentConnection.defineXML(xmldoc)
        logging.info("Starting VM..")
        self.start_vm(vm_id)


    def start_vm(self, vm_id):
        try:
            vm = self.currentConnection.lookupByName(vm_id)
        except libvirt.libvirtError as e:
            # Error code 42 = Domain not found
            if (e.get_error_code() == 42):
                print(e)
            else:
                raise(e)

        if vm.isActive():
            logging.info(f"VM '{vm_id}' already started")

        while not vm.isActive():
            logging.info(f"Starting VM '{vm_id}'")
            vm.create()

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
    

    def __create_cloudinit_iso(self, vmdir, cloudinit_yaml_file_path, cloudinit_network_yaml_file_path=""):

        # Validate the yaml file
        logging.debug("Validating Cloudinit config yaml.")
        process = subprocess.Popen(['cloud-init', 'devel', 'schema', '--config-file', cloudinit_yaml_file_path], 
                           stdout=subprocess.PIPE,
                           universal_newlines=True)
        output = process.stdout.readline()
        print(output.strip())
        # Do something else
        return_code = process.poll()
        logging.debug(f"SUBPROCESS RETURN CODE: {return_code}")
        if return_code is not None:
            # There was an issue with the cloud init file
            #TODO: Condition on error
            # Process has finished, read rest of the output 
            for output in process.stdout.readlines():
                print(output.strip())

        if cloudinit_network_yaml_file_path:
            logging.debug("Validating Cloudinit Network config yaml.")
            process = subprocess.Popen(['cloud-init', 'devel', 'schema', '--config-file', cloudinit_network_yaml_file_path], 
                            stdout=subprocess.PIPE,
                            universal_newlines=True)
            output = process.stdout.readline()
            print(output.strip())
            # Do something else
            return_code = process.poll()
            logging.debug(f"SUBPROCESS RETURN CODE: {return_code}")
            if return_code is not None:
                # There was an issue with the cloud init network file
                #TODO: Condition on error
                # Process has finished, read rest of the output 
                for output in process.stdout.readlines():
                    print(output.strip())

        # Create cloud_init disk image
        cloudinit_iso_path = f"{vmdir}/cloudinit.iso"

        args = ['cloud-localds', '-v', cloudinit_iso_path, cloudinit_yaml_file_path]

        if cloudinit_network_yaml_file_path:
            args.append(f"--network-config={cloudinit_network_yaml_file_path}")
            #args.append(cloudinit_network_yaml_file_path)

        print(args)

        process = subprocess.Popen(args, 
                           stdout=subprocess.PIPE,
                           universal_newlines=True)
        output = process.stdout.readline()
        print(output.strip())
        # Do something else
        return_code = process.poll()
        logging.debug(f"SUBPROCESS RETURN CODE: {return_code}")
        if return_code is not None:
            # There was an issue with the cloud init file
            #TODO: Condition on error
            # Process has finished, read rest of the output 
            for output in process.stdout.readlines():
                print(output.strip())
        logging.debug(f"Created cloudinit iso: {cloudinit_iso_path}")

        return cloudinit_iso_path

    def __generate_vm_id(self):
        return "vm-" + str(uuid.uuid1()).replace("-", "")[0:8]

    def __generate_mac_addr(self):
        mac = [ 0x00, 0x16, 0x3e,
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0xff),
            random.randint(0x00, 0xff) ]
        return ':'.join(map(lambda x: "%02x" % x, mac))

    def __generate_vm_path(self, account_id, vm_id):
        vm_path = f"{VM_ROOT_DIR}/{account_id}/{vm_id}"
        pathlib.Path(vm_path).mkdir(parents=True, exist_ok=True)
        return vm_path

    def __delete_vm_path(self, account_id, vm_id):
        tmp_path = f"{VM_ROOT_DIR}/{account_id}/{vm_id}"
