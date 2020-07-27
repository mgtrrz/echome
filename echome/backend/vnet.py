import time
import logging
import ipaddress
import string
from backend.id_gen import IdGenerator
from backend.user import User
from backend.database import dbengine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, MetaData, DateTime, TEXT, ForeignKey, create_engine, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import select, func
from sqlalchemy.ext.hybrid import hybrid_property
import sqlalchemy as db

from sqlalchemy import inspect

Base = declarative_base()

class VirtualNetworkObject(Base):
    __tablename__ = "virtual_networks"
    metadata = MetaData()

    id = Column(Integer, primary_key=True)
    vnet_id = Column(String(25), unique=True)
    account = Column(String(25))
    profile_name = Column(String(50))
    type = Column(String(25))
    created = Column(DateTime(timezone=True), server_default=func.now())
    config = Column(JSONB)
    active = Column(Boolean, default=True)
    tags = Column(JSONB)

    def init_table(self):
        self.metadata.create_all(dbengine.engine)
    
    # Save changes made to this object
    def commit(self):
        dbengine.session.add(self)
        dbengine.session.commit()
    
    # Delete this object from the database
    def delete(self):
        dbengine.session.delete(self)
        dbengine.session.commit()
    
    # Checks to see if the IP provided for a VM is valid for this network
    def validate_ip(self, ip: string):
        network_addr = f'{self.config["network"]}/{self.config["prefix"]}'
        logging.debug(f"Checking network address: {network_addr} for network {self.profile_name}")
        network = ipaddress.ip_network(f'{self.config["network"]}/{self.config["prefix"]}')
        hosts = network.hosts()

        ip_obj = self.valid_ip_format(ip)
        if ip_obj is False:
            raise ValueError("Provided Ip address is not valid.")

        if ip_obj not in hosts:
            logging.debug(f"{ip} is not a valid address for network {network_addr}")
            return False

        logging.debug(f"{ip} valid for network {network_addr}")
        return True

    # Checks to see if this is a valid IP address 
    def valid_ip_format(self, ip: string):
        try:
            ip_object = ipaddress.ip_address(ip)
        except ValueError:
            return False
        
        return ip_object

    def __str__(self):
        return self.vnet_id

class VirtualNetwork():

    valid_network_types = (
        "BridgeToLan",
        "NAT"
    )
    
    # Network: "192.168.15.0"
    # Prefix: "24"
    # Gateway: "192.168.15.1"
    # DnsServers: ["1.1.1.1", "1.0.0.1"]
    # Bridge: "br0"
    # Tags: {"Environment": "Home"}
    create_required_options = ("Network", "Prefix", "Gateway", "DnsServers", "Bridge")
    create_optionals = ("Tags")
    def create(self, Name: string, User: User, Type: string, **kwargs):
        logging.debug("Creating new network")
        if Type not in self.valid_network_types:
            raise InvalidNetworkType("Specified type is not a valid network type.")

        # Check to see if a network with that name does not already exist
        logging.debug("Checking if network with the name already exists..")
        vnet = dbengine.session.query(VirtualNetworkObject).filter_by(
            account=User.account,
            profile_name=Name
        ).first()
        if vnet:
            raise InvalidNetworkName("Network configuration with that name already exists.")

        # Validate the information provided is correct (Actual IP addresses)
        logging.debug("Validating provided network information..")
        try:
            network_cidr = f'{kwargs["Network"]}/{kwargs["Prefix"]}'
            logging.debug(f"Created network cidr with provided information {network_cidr}")

            if ipaddress.ip_address(kwargs["Gateway"]) not in ipaddress.ip_network(network_cidr).hosts():
                raise InvalidNetworkConfiguration("Cannot verify network configuration with provided information")
            
            for dns_server in kwargs["DnsServers"]:
                ipaddress.ip_address(dns_server)

        except ValueError as e:
            raise InvalidNetworkConfiguration("Cannot verify network configuration with provided information. Is the IP address space correct?")

        vnet_id = IdGenerator.generate("vnet")
        logging.debug(f"Creating new virtual network with Id: {vnet_id}")
        
        config = {
            "network": kwargs["Network"],
            "prefix": kwargs["Prefix"],
            "gateway": kwargs["Gateway"],
            "dns_servers": kwargs["DnsServers"],
            "bridge_interface": kwargs["Bridge"],
        }

        network = VirtualNetworkObject(
            vnet_id      = vnet_id,
            account      = User.account,
            profile_name = Name,
            type         = Type,
            config       = config,
            tags         = kwargs["Tags"] if "tags" in kwargs else {}
        )
        network.commit()
        return network

    def get_network(self, vnet_id: string, user: User):
        return dbengine.session.query(VirtualNetworkObject).filter_by(
            vnet_id=vnet_id,
            account=user.account
        ).first()
    
    def get_network_by_profile_name(self, profile_name: string, user: User):
        return dbengine.session.query(VirtualNetworkObject).filter_by(
            profile_name=profile_name,
            account=user.account
        ).first()
    
    def get_all_networks(self, user: User):
        return dbengine.session.query(VirtualNetworkObject).filter_by(
            account=user.account
        ).all()

    # can delete by either vnet_id or VirtualNetworkObject
    def delete_network(self, vnet_id: string = None, vnet: VirtualNetworkObject = None):
        vnet_obj = None
        if vnet_id:
            vnet_obj = self.get_network(vnet_id)
        
        if vnet:
            vnet_obj = vnet
        
        if vnet_obj is None:
            logging.debug(f"No network to delete, vnet_obj is None")
        
        vnet_obj.delete()

class InvalidNetworkName(Exception):
    pass

class InvalidNetworkType(Exception):
    pass

class InvalidNetworkConfiguration(Exception):
    pass
