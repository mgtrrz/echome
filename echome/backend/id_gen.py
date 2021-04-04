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
            l = default_vm_length if length == "" else length 
        elif type  == "vmi":
            prefix = "vmi-"
            l = default_vmi_length if length == "" else length 
        else:
            prefix = f"{type}-"
            len = default if length == "" else length 

        uuid = str(uuid.uuid4()).replace("-", "")
        if l > len(uuid):
            l = len(uuid)
        uid = uuid[0:l]
        return f"{prefix}{uid}"
