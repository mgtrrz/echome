from enum import Enum, auto

PROPERTIES = {
    "VM": {
        "VIRTUAL_MACHINE": {
            "shorthand": "vm",
            "length": 8,
        },
        "VIRTUAL_MACHINE_IMAGE": {
            "shorthand": "vmi",
            "length": 12,
        }
    },
    "IDENTITY": {
        "USER": {
            "shorthand": "user",
        },
        "ACCESS_KEY": {
            "shorthand": "auth",
        },
        "SERVICE_KEY": {
            "shorthand": "svc",
        }
    }
}

class SubEnum():
    def shorthand(self):
        print(self)
        return "yes!"

    @staticmethod
    def i():
        pass


class Service():
    class VM(SubEnum):
        class VIRTUAL_MACHINE:
            def __init__(self):
                return 
        VIRTUAL_MACHINE_IMAGE = SubEnum.i()
    
    class IDENTITY(SubEnum):
        USER = 1
        ACCESS_KEY = 2
        SERVICE_KEY = 3
    
    class NETWORK(SubEnum):
        VIRTUAL_NETWORK = 1
    
    class KUBE(SubEnum):
        KUBE = 1

class Attributes():
    service: Service = None

    def __init__(self, service: Service) -> None:
        self.service = service 

    @property
    def shorthand(self):
        return self._shorthand

    @shorthand.getter
    def shorthand(self):
        return PROPERTIES[self.service.name]

# class Services(BaseService):
#     VM = auto()
#     IDENTITY = auto()
#     SSHKEYS = auto()
#     NETWORK = auto()
#     KUBE = auto()
