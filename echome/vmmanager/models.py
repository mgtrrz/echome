import sshpubkeys
import logging
from django.db import models
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from echome.exceptions import AttemptedOverrideOfImmutableIdException
from echome.id_gen import IdGenerator
from identity.models import User

class HostMachines(models.Model):
    host_id = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=40)
    ip = models.GenericIPAddressField()
    created = models.DateTimeField(auto_now_add=True, null=False)
    metadata = models.JSONField(default=dict)
    tags = models.JSONField(default=dict)

    def __str__(self) -> str:
        return self.name

class UserKeys(models.Model):
    key_id = models.CharField(max_length=20, unique=True, db_index=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id")
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=50)
    service_key = models.BooleanField(default=False)
    service_owner = models.CharField(max_length=40, null=True)
    fingerprint = models.TextField()
    public_key = models.TextField()
    tags = models.JSONField(default=dict)

    def generate_sshkey(self, user:User, key_name:str, service_key=False):
        if self.name is not None or self.name != "":
            self.key_id = IdGenerator.generate("key")
        else:
            raise AttemptedOverrideOfImmutableIdException

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
            result = self.store(user, key_name, public_key)
            result["PrivateKey"] = private_key

        except KeyNameAlreadyExists as e:
            raise KeyNameAlreadyExists(e)

        return result

    def generate_id(self):
        if self.key_id is None or self.key_id == "":
            self.key_id = IdGenerator.generate("key")
        else:
            raise AttemptedOverrideOfImmutableIdException
    
    def store_key(self, user:User, key_name:str, public_key:str):
        # Check to make sure that we haven't already imported this key by
        # checking its MD5
        sshkey_obj = sshpubkeys.SSHKey(public_key)
        new_md5 = sshkey_obj.hash_md5()

        # Check if the key with this KeyName already exists
        try_key = UserKeys.objects.get(
            account=user.account,
            name=key_name
        )

        try_key = dbengine.session.query(KeyObject).filter_by(
            account=User.account,
            key_name=KeyName
        ).first()
        if try_key:
            logging.error(f"Key with that name already exists. key_name={KeyName}")
            raise KeyNameAlreadyExists(f"Key with that name already exists.")
            
        try_key = dbengine.session.query(KeyObject).filter_by(
            account=User.account,
            fingerprint=new_md5
        ).first()
        if try_key:
            logging.error(f"Key with that fingerprint already exists. key_name={KeyName}")
            raise PublicKeyAlreadyExists(f"Key with that fingerprint already exists.")

        newkey = KeyObject(
            account = User.account,
            key_id = IdGenerator.generate("key"),
            account_user = User.user_id,
            key_name = KeyName,
            fingerprint = new_md5,
            public_key = PublicKey
        )

        newkey.commit()
        return {
            "key_name": KeyName,
            "key_id": newkey.key_id,
            "fingerprint": newkey.fingerprint,
        }

    def __str__(self) -> str:
        return self.key_id

class VirtualMachines(models.Model):
    instance_id = models.CharField(max_length=20, unique=True, db_index=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id")
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    host = models.ForeignKey(HostMachines, on_delete=models.CASCADE)
    instance_type = models.CharField(max_length=40)
    instance_size = models.CharField(max_length=40)
    image_metadata = models.JSONField()
    interfaces = models.JSONField()
    storage = models.JSONField()
    key_name = models.CharField(max_length=50)
    firewall_rules = models.JSONField(null=True)
    tags = models.JSONField(default=dict)

    def __str__(self) -> str:
        return self.instance_id

class InstanceDefinition(models.Model):
    instance_definition_id = models.CharField(max_length=20, unique=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    host = models.ForeignKey(HostMachines, on_delete=models.CASCADE)
    instance_type = models.CharField(max_length=40)
    instance_size = models.CharField(max_length=40)
    cpu = models.CharField(max_length=40)
    memory = models.CharField(max_length=40)
    tags = models.JSONField(default=dict)

    def __str__(self) -> str:
        return self.instance_id

class KeyDoesNotExist(Exception):
    pass

class KeyNameAlreadyExists(Exception):
    pass

class PublicKeyAlreadyExists(Exception):
    pass

class OverridingKeyObject(Exception):
    pass