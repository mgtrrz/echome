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
            l = default_vm_length if length == "" else length 
        elif type  == "vmi":
            l = default_vmi_length if length == "" else length 
        else:
            l = default if length == "" else length 

        uid = str(uuid.uuid4()).replace("-", "")
        if l > len(uid):
            l = len(uid)
        uid = uid[0:l]
        return f"{type}-{uid}"
