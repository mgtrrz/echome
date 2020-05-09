from database import Database
import sshpubkeys
import logging
from sqlalchemy import select, and_

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
            return {
                "success": False,
                "meta_data": {
                    "key_name": key_name
                },
                "reason": "Key with that name already exists.",
            }
        
        stmt = db.user_keys.insert().values(
            account=user_obj["account_id"], 
            account_user=user_obj["account_user_id"], 
            key_name=key_name, 
            fingerprint=sshkey_obj.hash_md5(), 
            public_key=key
        )
        result = db.connection.execute(stmt)
        if result:
            return {
                "success": True,
                "meta_data": {
                    "key_name": key_name
                },
                "reason": "",
            }
    
    @staticmethod
    def get_key(user_obj, key_name):
        db = Database()

        select_stmt = select(
            [db.user_keys.c.public_key]
        ).where(
            and_(
                db.user_keys.c.account == user_obj["account_id"], 
                db.user_keys.c.key_name == key_name
            )
        )
        results = db.connection.execute(select_stmt).fetchall()
        if results:
            return results[0][0]