import uuid

default_vm_length = 8
default_vmi_length = 8
default = 8

class IdGenerator:
    # Generate a unique ID.
    @staticmethod
    def generate(type="vm", length=""):
        # Use default length unless length is manually specified
        if type == "vm":
            prefix = "vm-"
            len = default_vm_length if length == "" else length 
        elif type  == "vmi":
            prefix = "vmi-"
            len = default_vmi_length if length == "" else length 
        else:
            prefix = f"{type}-"
            len = default if length == "" else length 

        uid = str(uuid.uuid1()).replace("-", "")[0:len]
        return f"{prefix}{uid}"
