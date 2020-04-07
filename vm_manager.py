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

    def createInstance(self, instanceType, instanceSize):

        config = {
            "cpu": instanceSizes[instanceType][instanceSize]["cpu"],
            "memory": instanceSizes[instanceType][instanceSize]["memory_megabytes"],
            "xml_template": instanceSizes[instanceType]["xml_template"]
        }

        xmldoc = self.__generate_new_vm_template(config)
        print(xmldoc)
        

    def __generate_new_vm_template(self, config):
        # TODO: Proper with file open so we can properly close it afterwards
        filein = open(f"./xml_templates/{config['xml_template']}")
        #read it
        src = Template(filein.read())
        #do the substitution
        replace = {
            'VM_NAME': str(uuid.uuid1()).replace("-", "")[0:16],
            'VM_CPU_COUNT': config["cpu"], 
            'VM_MEMORY': config["memory"], 
        }
        return src.substitute(replace)