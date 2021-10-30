import time
import logging
import hvac
from echome.config import AppConfig

class Vault:
    client = None

    def __init__(self):
        config = AppConfig()
        self.client = hvac.Client(
            url=config.Vault().addr, 
            token=config.Vault().token
        )
    
    def store_sshkey(self, mount_point:str, path_name:str, key:str):

        self.client.secrets.kv.v2.create_or_update_secret(
            mount_point=mount_point,
            path=path_name,
            secret={
                "private_key": key
            },
        )
    
    def store_dict(self, mount_point:str, path_name:str, value:dict):
        self.client.secrets.kv.v2.create_or_update_secret(
            mount_point=mount_point,
            path=path_name,
            secret=value,
        )
    
    # When given a path, this will list all the keys in the path
    # and call delete_key on each entry.
    def delete_kv_dir(self, mount_point:str, path_name:str):
        keys = self.list_keys(mount_point, path_name)
        if keys:
            for key in keys:
                self.delete_key(mount_point, f"{path_name}/{key}")
    
    # When provided the full path to a key, deletes all metadata
    # and versions of the key.
    def delete_key(self, mount_point:str, path_name:str):
        self.client.secrets.kv.v2.delete_metadata_and_all_versions(
            mount_point=mount_point,
            path=path_name
        )
    
    def list_keys(self, mount_point:str, path_name:str):
        try:
            keys = self.client.secrets.kv.v2.list_secrets(
                mount_point=mount_point,
                path=path_name
            )
            return keys['data']['keys']
        except:
            return False
    
    def get_secret(self, mount_point:str, path_name:str):
        return self.client.secrets.kv.v2.read_secret_version(
            mount_point=mount_point,
            path=path_name
        )
    
    def create_policy(self, policy:str, name:str):
        return self.client.sys.create_or_update_policy(
            name=name,
            policy=policy,
        )
    
    def delete_policy(self, name:str):
        return self.client.sys.delete_policy(name)
    
    def generate_temp_token(self, policies:list, lease='1h'):
        return self.client.create_token(
            policies=policies, 
            lease=lease, 
            renewable=False
        )