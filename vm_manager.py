import libvirt
from string import Template
import uuid

instanceSizes = {
    "standard": {
        "nano": {
            "cpu": 1,
            "memory_megabytes": 512,
        },
        "micro": {
            "cpu": 1,
            "memory_megabytes": 1024,
        },
        "small": {
            "cpu": 2,
            "memory_megabytes": 2048,
        },
        "medium": {
            "cpu": 2,
            "memory_megabytes": 4096,
        },
        "large": {
            "cpu": 4,
            "memory_megabytes": 4096,
        },
        "xlarge": {
            "cpu": 8,
            "memory_megabytes": 8192,
        },
        "xml_template": "create_vm.xml"
    }
}

class vmManager:

    def __init__(self):
        self.currentConnection = libvirt.open('qemu:///system')

    def getConnection(self):
        return self.currentConnection

    def closeConnection(self):
        self.currentConnection.close()

    def createInstance(self, instanceType, cloudInitConfig=""):
        
        # If we have Cloud-init config, build and test it

        # cloudInitConfig = {
        #     "path": "/test/just/testing"
        # }

        iType = instanceType[0]
        iSize = instanceType[1]

        config = {
            "cpu": instanceSizes[iType][iSize]["cpu"],
            "memory": instanceSizes[iType][iSize]["memory_megabytes"],
            "xml_template": instanceSizes[iType]["xml_template"],
            "cloud_init_path": None,
        }

        xmldoc = self.__generate_new_vm_template(config)
        standard_cloudinit_config = self.__generate_cloudinit_config(config)

        print(xmldoc)
        print(standard_cloudinit_config)
    

    def __generate_new_vm_template(self, config):

        cloudinit_xml = ""
        
        if config["cloud_init_path"]:
            with open(f"./xml_templates/cloudinit_disk.xml", 'r') as filehandle:
                cloudinit_xml = Template(filehandle.read())
                replace = {
                    'VM_USER_CLOUDINIT_IMG_PATH': config["cloud_init_path"]
                }
                cloudinit_xml = cloudinit_xml.substitute(replace)

        with open(f"./xml_templates/{config['xml_template']}", 'r') as filehandle:
            src = Template(filehandle.read())
            replace = {
                'VM_NAME': str(uuid.uuid1()).replace("-", "")[0:16],
                'VM_CPU_COUNT': config["cpu"], 
                'VM_MEMORY': config["memory"],
                'CLOUDINIT_DISK': cloudinit_xml
            }
            return src.substitute(replace)
    
    def __generate_cloudinit_config(self, config):
        cloud_init = """#cloud-config
chpasswd: { expire: False }
ssh_pwauth: False
hostname: test
ssh_authorized_keys:
        """

        return cloud_init