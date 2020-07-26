import time
import logging
from backend.id_gen import IdGenerator
from backend.user import User
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, MetaData, DateTime, TEXT, ForeignKey, create_engine, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import select, func
from sqlalchemy.ext.hybrid import hybrid_property
import sqlalchemy as db
import string

from .database import DbEngine

Base = declarative_base()

class VirtualNetworkObject(Base):
    __tablename__ = "virtual_networks"
    metadata = MetaData()

    session = None

    id = Column(Integer, primary_key=True)
    vnet_id = Column(String(25), unique=True)
    account = Column(String(25))
    profile_name = Column(String(50))
    type = Column(String(25))
    created = Column(DateTime(timezone=True), server_default=func.now())
    config = Column(JSONB)
    active = Column(Boolean, default=True)
    tags = Column(JSONB)

    def init_session(self):
        dbengine = DbEngine()
        self.session = dbengine.return_session()
        self.metadata.create_all(dbengine.engine)
        return self.session
    
    def commit(self):
        if not self.session:
            self.init_session()
        
        self.session.add(self)
        self.session.commit()

    def __str__(self):
        return self.vnet_id

class VirtualNetwork():

    _valid_network_types = [
        "BridgeToLan",
        "NAT"
    ]
    
    # Network: "192.168.15.0"
    # Netmask: "24"
    # Gateway: "192.168.15.1"
    # DnsServers: ["1.1.1.1", "1.0.0.1"]
    # Tags: {"Environment": "Home"}
    create_options = ("Network", "Netmask", "Gateway", "DnsServers", "Tags")
    def create(self, Name: string, User: User, Type: string, **kwargs):
        if Type not in self._valid_network_types:
            raise InvalidNetworkType("Specified type is not a valid network type.")

        network = VirtualNetwork()
        vnet_id = IdGenerator.generate("vnet")
        logging.debug(f"Creating new virtual network with Id: {vnet_id}")
        
        config = {
            "network": kwargs["Network"],
            "netmask": kwargs["Netmask"],
            "gateway": kwargs["Gateway"],
            "dns_servers": kwargs["DnsServers"]
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

    def get_network(self, vnet_id: string):
        network = VirtualNetworkObject()
        session = network.init_session()
        return session.query(VirtualNetworkObject).filter_by(vnet_id=vnet_id).first()

class InvalidNetworkType(Exception):
    pass