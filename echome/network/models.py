import logging
import ipaddress
from django.db import models
from identity.models import User
from echome.id_gen import IdGenerator
from echome.exceptions import AttemptedOverrideOfImmutableIdException

logger = logging.getLogger(__name__)

# Create your models here.
class VirtualNetwork(models.Model):
    network_id = models.CharField(max_length=20, unique=True, db_index=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id")
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)

    name = models.CharField(max_length=40, null=False)
    class Type(models.TextChoices):
        BRIDGE_TO_LAN = 'BTL', 'BridgeToLan'
        NAT = 'NAT', 'NetworkAddressTranslation'

    type = models.CharField(
        max_length=4,
        choices=Type.choices,
        default=Type.BRIDGE_TO_LAN,
    )
    config = models.JSONField(default=dict)
    deactivated = models.BooleanField(default=False, null=False)
    tags = models.JSONField(default=dict)

    def generate_id(self):
        if self.network_id is None or self.network_id == "":
            self.network_id = IdGenerator.generate("vnet")
        else:
            raise AttemptedOverrideOfImmutableIdException

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
    
    # Network: "192.168.15.0"
    # Prefix: "24"
    # Gateway: "192.168.15.1"
    # DnsServers: ["1.1.1.1", "1.0.0.1"]
    # Bridge: "br0"
    # Tags: {"Environment": "Home"}
    def create(self, name:str, user:User, type:Type,
            network:str, prefix:str, gateway:str, dns_servers:list,
            bridge:str = None, tags:list = None):
        logger.debug("Creating new network")

        self.generate_id()

        # Check to see if a network with that name does not already exist
        logger.debug("Checking if network with the name already exists..")
        if VirtualNetwork.objects.filter(account=user.account, name=name).exists():
            raise InvalidNetworkName("Network configuration with that name already exists.")

        # Validate the information provided is correct (Actual IP addresses)
        logger.debug("Validating provided network information..")
        try:
            network_cidr = f'{network}/{prefix}'
            logger.debug(f"Created network cidr with provided information {network_cidr}")

            if ipaddress.ip_address(gateway) not in ipaddress.ip_network(network_cidr).hosts():
                raise InvalidNetworkConfiguration("Supplied gateway address not in provided network")
            
            for dns_server in dns_servers:
                ipaddress.ip_address(dns_server)

        except ValueError as e:
            raise InvalidNetworkConfiguration("Cannot verify network configuration with provided information. Is the IP address space correct?")

        logger.debug(f"Creating new virtual network with Id: {self.network_id}")
        
        config = {
            "network": network,
            "prefix": prefix,
            "gateway": gateway,
            "dns_servers": dns_servers,
            "bridge_interface": bridge,
        }

        self.account = user.account
        self.name = name
        self.type = type
        self.config = config
        self.tags = tags
        
        self.save()
        return self.network_id

    def __str__(self) -> str:
        return self.network_id

class InvalidNetworkName(Exception):
    pass

class InvalidNetworkType(Exception):
    pass

class InvalidNetworkConfiguration(Exception):
    pass
