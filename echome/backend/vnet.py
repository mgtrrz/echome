class NetworkBase:
    pass

class VirtualNetwork:
    pass

class VirtualNetworkBridgeToLan(NetworkBase):

    def using_profile(self, profile=""):
        pass

    def __str__(self):
        return "BridgeToLan"
    pass


class VirtualNetworkNat(NetworkBase):

    def __str__(self):
        return "NAT"
    pass

