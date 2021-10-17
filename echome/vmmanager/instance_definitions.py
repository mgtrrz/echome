import logging

logger = logging.getLogger(__name__)

# 'InstanceType' or definition refers to the entire string: 'standard.medium'.
# 'InstanceClass' or 'class' refers to 'standard'
# 'InstanceSize' or 'size' refers to 'medium'
class InstanceDefinition:
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
        }
    }

    def __init__(self, instance_class, instance_size):
        if not instance_class in self.instanceSizes:
            logger.error(f"Provided instance type is not a valid option: {instance_class}")
            raise InvalidInstanceType("Provided instance class is not a valid option.")

        if not instance_size in self.instanceSizes[instance_class]:
            logger.error(f"Provided instance size is not a valid option: {instance_class}.{instance_size}")
            raise InvalidInstanceType("Provided instance size is not a valid option.")

        self._class = instance_class
        self._size = instance_size


    def __str__(self):
        return f"{self._class}.{self._size}"

    def get_all_configurations(self):
        return self.instanceSizes

    def get_class(self):
        return self._class

    def get_size(self): 
        return self._size

    def get_cpu(self):
        return self.instanceSizes[self._class][self._size]["cpu"]
    
    def get_memory(self):
        return self.instanceSizes[self._class][self._size]["memory_megabytes"]
    
    @property
    def instance_class(self):
        return self._class

    @property
    def instance_size(self): 
        return self._size

    @property
    def cpu(self):
        return self.instanceSizes[self._class][self._size]["cpu"]
    
    @property
    def memory(self):
        return self.instanceSizes[self._class][self._size]["memory_megabytes"]
    

class InvalidInstanceType(Exception):
    pass
