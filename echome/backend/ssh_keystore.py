import sshpubkeys
import logging
from sqlalchemy import select, and_
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from .database import Database
from .id_gen import IdGenerator

class KeyStore:

    @staticmethod
    def create_key(user_obj, key_name):
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
            result = KeyStore.store_key(user_obj, key_name, public_key)
            result["PrivateKey"] = private_key
        except KeyNameAlreadyExists as e:
            raise KeyNameAlreadyExists(e)

        return result

    @staticmethod
    def store_key(user_obj, key_name, key):
        db = Database()

        sshkey_obj = sshpubkeys.SSHKey(key)

        # Check to make sure a key with this name doesn't already exist
        select_stmt = select(
            [db.user_keys.c.key_name]
        ).where(
            and_(
                db.user_keys.c.account == user_obj.account, 
                db.user_keys.c.key_name == key_name
            )
        )
        results = db.connection.execute(select_stmt).fetchall()
        if results:
            logging.error(f"Key with that name already exists. key_name={key_name}")
            raise KeyNameAlreadyExists(f"Key with that name already exists.")

        # Check to make sure that we haven't already imported this key by
        # checking its MD5
        new_md5 = sshkey_obj.hash_md5()

        select_stmt = select(
            [db.user_keys.c.fingerprint]
        ).where(
            and_(
                db.user_keys.c.account == user_obj.account, 
                db.user_keys.c.fingerprint == new_md5
            )
        )
        results = db.connection.execute(select_stmt).fetchall()
        if results:
            logging.error(f"Key with that fingerprint already exists. key_name={key_name}")
            raise PublicKeyAlreadyExists(f"Key with that fingerprint already exists.")

        # Store the new key
        new_id = IdGenerator.generate("key")
        logging.debug(f"Generating new key id: {new_id}")

        stmt = db.user_keys.insert().values(
            account=user_obj.account, 
            account_user=user_obj.user_id, 
            key_id=new_id,
            key_name=key_name, 
            fingerprint=new_md5, 
            public_key=key
        )
        result = db.connection.execute(stmt)
        if result:
            return {
                "key_name": key_name,
                "key_id": new_id,
                "fingerprint": new_md5,
            }
    
    @staticmethod
    def get_key(user_obj, key_name, get_public_key=True):
        db = Database()

        if get_public_key:
            columns = [
                db.user_keys.c.key_id,
                db.user_keys.c.key_name, 
                db.user_keys.c.fingerprint,
                db.user_keys.c.public_key, 
            ]
        else:
            columns = [
                db.user_keys.c.key_id,
                db.user_keys.c.key_name, 
                db.user_keys.c.fingerprint,
            ]

        select_stmt = select(columns).where(
            and_(
                db.user_keys.c.account == user_obj.account, 
                db.user_keys.c.key_name == key_name
            )
        )
        results = db.connection.execute(select_stmt).fetchall()

        keys = []
        if results:
            key_meta = {}
            i = 0
            for column in columns:
                key_meta[column.name] = results[0][i]
                i += 1
            keys.append(key_meta)

            return keys
        else:
            raise KeyDoesNotExist("Specified key name does not exist.")

    @staticmethod
    def get_all_keys(user_obj):
        db = Database()

        columns = [
            db.user_keys.c.key_id,
            db.user_keys.c.key_name, 
            db.user_keys.c.fingerprint,
        ]

        select_stmt = select(columns).where(
            db.user_keys.c.account == user_obj.account
        )
        results = db.connection.execute(select_stmt).fetchall()
        if results:
            keys = []
            for row in results:
                key_meta = {}
                i = 0
                for column in columns:
                    key_meta[column.name] = row[i]
                    i += 1
                keys.append(key_meta)

            return keys

    
    @staticmethod
    def delete_key(user_obj, key_name):
        try:
            result = KeyStore.get_key(user_obj, key_name, get_public_key=False)
        except KeyDoesNotExist as e:
            raise KeyDoesNotExist(e)

        db = Database()

        print(result)

        # delete entry in db
        del_stmt = db.user_keys.delete().where(db.user_keys.c.key_id == result[0]["key_id"])
        db.connection.execute(del_stmt)
        return {"success": True}
    
    @staticmethod
    def get_public_key_vm_metadata(key_name, vm_metadata):
        db = Database()

        select_stmt = select([db.user_keys.c.public_key]).where(
            and_(
                db.user_keys.c.account == vm_metadata["account"],
                db.user_keys.c.key_name == key_name
            )
        )
        results = db.connection.execute(select_stmt).fetchall()

        if results:
            return results[0][0]
        else:
            raise KeyDoesNotExist("Specified key name does not exist.")



class KeyDoesNotExist(Exception):
    pass

class KeyNameAlreadyExists(Exception):
    pass

class PublicKeyAlreadyExists(Exception):
    pass