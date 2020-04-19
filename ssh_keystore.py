from database import Database
import sshpubkeys

class EchKeystore:

    def store_key(self, database_conneciton_obj: Database, user_obj, key_name, key):

        sshkey_obj = sshpubkeys.SSHKey(key)

        query = """
        INSERT INTO user_keys (
            account, 
            created, 
            account_user, 
            key_name, 
            fingerprint, 
            public_key
        )
        VALUES (
            %s, 
            'now', 
            %s, 
            %s, 
            %s, 
            %s
        )
        """
        data = (
            user_obj["account_id"],
            user_obj["account_user_id"],
            key_name,
            sshkey_obj.hash_md5(),
            key,
        )
        print(data)
        database_conneciton_obj.insert(query, data)