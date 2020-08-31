import time
import logging
import hvac
from backend.config import AppConfig

class Vault:
    client = None

    def __init__(self):
        config = AppConfig()
        self.client = hvac.Client(
            url=config.Vault().addr, 
            token=config.Vault().token
        )
    
    def store_sshkey(self, path_name:str, key:str):

        self.client.secrets.kv.v2.create_or_update_secret(
            mount_point="sshkeys",
            path=path_name,
            secret={
                "private_key": key
            },
        )
    