import xmltodict
import logging
from typing import List
from enum import Enum
from dataclasses import dataclass, field
# from .models import VirtualNetwork
# from echome.config import ecHomeConfig

logger = logging.getLogger(__name__)


# <network>
#   <name>examplenetwork</name>
#   <bridge name="virbr100" />
#   <forward mode="route" />
#   <ip address="10.10.120.1" netmask="255.255.255.0" />
# </network>

@dataclass
class NetworkXmlObject():

    class ForwardMode(Enum):
        NAT = "nat"
        ROUTE = "route"
        OPEN = "open"
        BRIDGE = "bridge"

    vnet_id: str
    bridge_name: str
    forward_mode: ForwardMode
    router_ip: str
    prefix: str

    # https://libvirt.org/formatnetwork.html
    def render_xml(self, pretty=True):
        obj = {
            'network': {
                'name': self.vnet_id,
                'bridge': {
                    "@name": self.bridge_name,
                },
                'forward': {
                    "@mode": self.forward_mode.value,
                },
                'ip': {
                    "@address": self.router_ip,
                    "@prefix": self.prefix,
                }
            }
        }

        return xmltodict.unparse(obj, full_document=False, pretty=pretty, short_empty_elements=True, indent="  ")


net = NetworkXmlObject(
    vnet_id="vnet-12345678",
    bridge_name="br0",
    forward_mode=NetworkXmlObject.ForwardMode.NAT,
    router_ip="172.16.9.1",
    prefix="24"
)

print(net.render_xml())
