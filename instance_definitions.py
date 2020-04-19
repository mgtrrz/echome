
class InstanceSizes:
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

    #def get_all_instance_sizes(self):
    #    return self.instanceSizes