import sshpubkeys
import logging
from sqlalchemy import select, and_
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from sqlalchemy import Table, Column, Integer, \
    String, MetaData, DateTime, TEXT, ForeignKey, create_engine, Boolean
from sqlalchemy.sql import select, func
from sqlalchemy.ext.declarative import declarative_base
from .database import Database, dbengine
from .id_gen import IdGenerator
from .user import User

Base = declarative_base()

class KeyObject(Base):
    __tablename__ = "user_keys"
    metadata = MetaData()

    id = Column("id", Integer, primary_key=True)
    account = Column("account", String(25))
    created = Column("created", DateTime(timezone=True), server_default=func.now())
    key_id =  Column("key_id", String(20), unique=True)
    account_user = Column("account_user", String(50))
    service_key = Column("service_key", Boolean)
    key_name = Column("key_name", String(50))
    fingerprint = Column("fingerprint", TEXT)
    public_key = Column("public_key", TEXT)

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

class KeyStore:

    def create_key(self, user_obj, key_name, service_key=False):
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

        try:
            result = self.store(user_obj, key_name, public_key)
            result["PrivateKey"] = private_key
        except KeyNameAlreadyExists as e:
            raise KeyNameAlreadyExists(e)

        return result

    def store(self, User: User, KeyName:str, PublicKey:str):
        # Check to make sure that we haven't already imported this key by
        # checking its MD5
        sshkey_obj = sshpubkeys.SSHKey(PublicKey)
        new_md5 = sshkey_obj.hash_md5()

        # Check if the key with this KeyName already exists
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
    
    def get(self, User:User, KeyName:str):
        
        key = dbengine.session.query(KeyObject).filter_by(
            account=User.account,
            key_name=KeyName
        ).first()

        if key:
            return key
        else:
            raise KeyDoesNotExist("Specified key name does not exist.")
    
    def get_all(self, User:User, show_svc_keys=False):
        # keys = dbengine.session.query(KeyObject).filter(
        #     KeyObject.account=User.account,
        #     or_(KeyObject.service_key=show_svc_keys, KeyObject.service_key is None)
        # ).all()
        keys = None

        return keys

class KeyDoesNotExist(Exception):
    pass

class KeyNameAlreadyExists(Exception):
    pass

class PublicKeyAlreadyExists(Exception):
    pass