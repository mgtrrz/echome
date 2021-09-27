import sshpubkeys
import logging
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from identity.models import User
from .models import UserKey
from .exceptions import *

logger = logging.getLogger(__name__)

class UserKeyManager:

    def generate_sshkey(self, user:User, key_name:str, service_key=False):
        """
        Generate an SSH key to save in the database.
        The private key is returned and not saved in the database.
        """
        key = rsa.generate_private_key(
            backend=crypto_default_backend(), 
            public_exponent=65537, 
            key_size=2048
        )
        private_key = key.private_bytes(
            crypto_serialization.Encoding.PEM, 
            crypto_serialization.PrivateFormat.TraditionalOpenSSL, 
            crypto_serialization.NoEncryption()
        ).decode("utf-8")
        public_key = key.public_key().public_bytes(
            crypto_serialization.Encoding.OpenSSH, 
            crypto_serialization.PublicFormat.OpenSSH
        ).decode("utf-8")

        self.name = key_name
        self.public_key = public_key
        self.service_key = service_key

        try:
            key_obj = self.store(user, key_name, public_key)
        except KeyNameAlreadyExists:
            raise
        except PublicKeyAlreadyExists:
            raise

        return key_obj, private_key
    
    def store_key(self, user:User, key_name:str, public_key:str):
        """
        Store a public key and fingerprint in the database
        """

        # Generate an MD5 with the provided public key
        sshkey_obj = sshpubkeys.SSHKey(public_key)
        new_md5 = sshkey_obj.hash_md5()

        # Check if the key with this KeyName already exists (unique
        # for an account)
        if UserKey.objects.filter(account=user.account, name=key_name).exists():
            logger.error(f"Key with that name already exists. key_name={key_name}")
            raise KeyNameAlreadyExists(f"Key with that name already exists.")
        
        # Check to make sure that we haven't already imported this 
        # key by checking its MD5
        if UserKey.objects.filter(account=user.account, fingerprint=new_md5).exists():
            logger.error(f"Key with that fingerprint already exists. key_name={key_name}")
            raise PublicKeyAlreadyExists(f"Key with that fingerprint already exists.")

        new_key = UserKey()

        new_key.generate_id()
        new_key.account = user.account
        new_key.name = key_name
        new_key.fingerprint = new_md5
        new_key.public_key = public_key

        try:
            new_key.save()
            return new_key
        except Exception as e:
            logger.error("Could not save new key to database!")
            raise e
