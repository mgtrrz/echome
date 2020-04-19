
class Instance:
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

    def __init__(self, instance_type="", instance_size=""):
        self.itype = instance_type
        self.isize = instance_size

    def get_cpu(self):
        return self.instanceSizes[self.itype][self.isize]["cpu"]
    
    def get_memory(self):
        return self.instanceSizes[self.itype][self.isize]["memory_megabytes"]
    
    def get_xml_template(self):
        return self.instanceSizes[self.itype]["xml_template"]