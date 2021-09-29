import logging
import ipaddress
from identity.models import User
from .models import VirtualNetwork
from .exceptions import InvalidNetworkConfiguration, InvalidNetworkName, InvalidNetworkType

logger = logging.getLogger(__name__)

class VirtualNetworkManager:
    # Checks to see if the IP provided for a VM is valid for this network
    def validate_ip(self, ip:str):
        network_addr = f'{self.config["network"]}/{self.config["prefix"]}'
        logger.debug(f"Checking network address: {network_addr} for network {self.name}")
        network = ipaddress.ip_network(f'{self.config["network"]}/{self.config["prefix"]}')
        hosts = network.hosts()

        ip_obj = self.valid_ip_format(ip)
        if ip_obj is False:
            raise ValueError("Provided Ip address is not valid.")

        if ip_obj not in hosts:
            logger.debug(f"{ip} is not a valid address for network {network_addr}")
            return False

        logging.debug(f"{ip} valid for network {network_addr}")
        return True

    # Checks to see if this is a valid IP address 
    def valid_ip_format(self, ip:str):
        try:
            ip_object = ipaddress.ip_address(ip)
        except ValueError:
            return False
        
        return ip_object
    
    def validate_network(self, network:str, prefix:str, gateway:str, dns_servers:list):
        logger.debug("Validating provided network information..")
        try:
            network_cidr = f'{network}/{prefix}'
            logger.debug(f"Created network cidr with provided information {network_cidr}")

            if ipaddress.ip_address(gateway) not in ipaddress.ip_network(network_cidr).hosts():
                raise InvalidNetworkConfiguration("Supplied gateway address not in provided network")
            
            for dns_server in dns_servers:
                ipaddress.ip_address(dns_server)
            
            return True
        except ValueError as e:
            return False
    
    # Network: "192.168.15.0"
    # Prefix: "24"
    # Gateway: "192.168.15.1"
    # DnsServers: ["1.1.1.1", "1.0.0.1"]
    # Bridge: "br0"
    # Tags: {"Environment": "Home"}
    def create_bridge_to_lan_network(self, name:str, user:User, type:VirtualNetwork.Type,
            network:str, prefix:str, gateway:str, dns_servers:list,
            bridge:str = None, tags:list = None):
        logger.debug("Creating new network")

        vnet = VirtualNetwork()

        vnet.generate_id()

        # Check to see if a network with that name does not already exist
        logger.debug("Checking if network with the name already exists..")
        if VirtualNetwork.objects.filter(account=user.account, name=name).exists():
            raise InvalidNetworkName("Network configuration with that name already exists.")

        # Validate the information provided is correct (Actual IP addresses)
        if not self.validate_network(network, prefix, gateway, dns_servers):
            raise InvalidNetworkConfiguration("Cannot verify network configuration with provided information. Is the IP address space correct?")

        logger.debug(f"Creating new virtual network with Id: {self.network_id}")
        
        config = {
            "network": network,
            "prefix": prefix,
            "gateway": gateway,
            "dns_servers": dns_servers,
            "bridge_interface": bridge,
        }

        vnet.account = user.account
        vnet.name = name
        vnet.type = type
        vnet.config = config
        vnet.tags = tags
        
        vnet.save()
        return vnet.network_id

    def create_nat_network(self):
        pass
