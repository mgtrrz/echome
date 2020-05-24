import sys

def resource(type):
    req_resource = getattr(sys.modules[__name__], type)
    return req_resource()

class vm:
    def __init__(self, session):
        self.session = ""

    def get_all_vms(self):
        pass