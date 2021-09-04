import logging

logger = logging.getLogger(__name__)

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
            "xml_template": "default_create_vm.xml"
        }
    }

    instance_configs = {
        "type": "standard",
        "sizes": [
            {
                "name": "nano",
                "cpu": 0.5,
                "memory_megabytes": 512,
            },
            {
                "name": "micro",
                "cpu": 1,
                "memory_megabytes": 1024,
            },
            {
                "name": "small",
                "cpu": 2,
                "memory_megabytes": 2048,
            },
            {
                "name": "medium",
                "cpu": 2,
                "memory_megabytes": 4096,
            },
            {
                "name": "large",
                "cpu": 4,
                "memory_megabytes": 4096,
            },
            {
                "name": "xlarge",
                "cpu": 8,
                "memory_megabytes": 8192,
            },
        ]
    }

    def __init__(self, instance_type="", instance_size=""):
        if not instance_type in self.instanceSizes:
            logger.error(f"Provided instance type is not a valid option: {instance_type}")
            raise InvalidInstanceType("Provided instance type is not a valid option.")

        if not instance_size in self.instanceSizes[instance_type]:
            logger.error(f"Provided instance size is not a valid option: {instance_type}.{instance_size}")
            raise InvalidInstanceType("Provided instance size is not a valid option.")

        self.itype = instance_type
        self.isize = instance_size

    def __str__(self):
        return f"{self.itype}.{self.isize}"

    def get_all_instance_configurations(self):
        return self.instanceSizes


    def get_cpu(self):
        return self.instanceSizes[self.itype][self.isize]["cpu"]
    
    def get_memory(self):
        return self.instanceSizes[self.itype][self.isize]["memory_megabytes"]
    
    def get_xml_template(self):
        return self.instanceSizes[self.itype]["xml_template"]

class InvalidInstanceType(Exception):
    pass