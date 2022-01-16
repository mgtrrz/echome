import logging
import hvac
from echome.config import ecHomeConfig
from .exceptions import CannotUnsealVaultServerError, VaultIsSealedError

logger = logging.getLogger(__name__)

class Vault:
    client = None

    def __init__(self):
        self.client = hvac.Client(
            url=ecHomeConfig.Vault().addr, 
            token=ecHomeConfig.Vault().root_token
        )
        self.unseal()
    

    @property
    def has_root(self) -> bool:
        capabilities = self.client.lookup_token()['data']
        return capabilities['path'] == 'auth/token/root'
    

    def unseal(self):
        """Unseals Vault"""
        if self.client.sys.is_sealed():
            if ecHomeConfig.Vault().key is not None:
                keys = [ecHomeConfig.Vault().key]
            else:
                raise VaultIsSealedError("There are no keys configure to unseal Vault.")

            logger.debug("Attempting to unseal")
            self.client.sys.submit_unseal_keys(keys=keys)
            if self.client.sys.is_sealed():
                raise CannotUnsealVaultServerError
        else:
            logger.debug("Vault is already unsealed!")
    

    def create_secret_engine(self, path:str, type:str = "kv"):
        logger.debug(f"Creating secrets engine of type: {type} at path {path}")
        options = {}
        if type == "kv":
            options['version'] = "2"

        self.client.sys.enable_secrets_engine(
            backend_type=type,
            path=path,
            options=options
        )
    
    def check_if_path_exists(self, path:str) -> bool:
        engines = self.client.sys.list_mounted_secrets_engines()['data']
        return f"{path}/" in engines.keys()
    

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


    def delete_kv_dir(self, mount_point:str, path_name:str):    
        """When given a path, this will list all the keys in the path
        and call delete_key on each entry."""
        keys = self.list_keys(mount_point, path_name)
        if keys:
            for key in keys:
                self.delete_key(mount_point, f"{path_name}/{key}")
    

    def delete_key(self, mount_point:str, path_name:str):
        """When provided the full path to a key, deletes all metadata
        and versions of the key."""
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
