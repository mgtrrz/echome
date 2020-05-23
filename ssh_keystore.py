from database import Database
import sshpubkeys
import logging
from sqlalchemy import select, and_
from id_gen import IdGenerator

class EchKeystore:

    @staticmethod
    def store_key(user_obj, key_name, key):
        db = Database()

        sshkey_obj = sshpubkeys.SSHKey(key)

        # Check to make sure a key with this name doesn't already exist
        select_stmt = select(
            [db.user_keys.c.key_name]
        ).where(
            and_(
                db.user_keys.c.account == user_obj["account_id"], 
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
                db.user_keys.c.account == user_obj["account_id"], 
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
            account=user_obj["account_id"], 
            account_user=user_obj["account_user_id"], 
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
            }
    
    @staticmethod
    def get_key(user_obj, key_name, get_public_key=True):
        db = Database()

        if get_public_key:
            columns = [
                db.user_keys.c.key_name, 
                db.user_keys.c.fingerprint,
                db.user_keys.c.public_key, 
            ]
        else:
            columns = [
                db.user_keys.c.key_name, 
                db.user_keys.c.fingerprint,
            ]

        select_stmt = select(columns).where(
            and_(
                db.user_keys.c.account == user_obj["account_id"], 
                db.user_keys.c.key_name == key_name
            )
        )
        results = db.connection.execute(select_stmt).fetchall()

        if results:
            key_meta = {}
            i = 0
            for column in columns:
                key_meta[column.name] = results[0][i]
                i += 1

            return key_meta
        else:
            raise KeyDoesNotExist("Specified key name does not exist.")

    @staticmethod
    def get_all_keys(user_obj):
        db = Database()

        columns = [
            db.user_keys.c.key_name, 
            db.user_keys.c.fingerprint,
        ]

        select_stmt = select(columns).where(
            db.user_keys.c.account == user_obj["account_id"]
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
        else:
            raise KeyDoesNotExist("Specified key name does not exist.")


class KeyDoesNotExist(Exception):
    pass

class KeyNameAlreadyExists(Exception):
    pass

class PublicKeyAlreadyExists(Exception):
    pass