import libvirt
from string import Template
import uuid
from instance_definitions import Instance

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

        vm_id = self.__generate_vm_id()

        # Generate cloudinit config
        cloudinit_params["vm_id"] = vm_id
        standard_cloudinit_config = self.__generate_cloudinit_config(cloudinit_params)

        # Generate VM
        vm_config = {
            "vm_id": vm_id,
            "cpu": instanceType.get_cpu(),
            "memory": instanceType.get_memory(),
            "xml_template": instanceType.get_xml_template(),
            "cloud_init_path": None,
        }
        xmldoc = self.__generate_new_vm_template(vm_config)

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

    def __generate_vm_id(self):
        return "vm-" + str(uuid.uuid1()).replace("-", "")[0:8]