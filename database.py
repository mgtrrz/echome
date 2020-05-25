import logging
from configparser import ConfigParser
from datetime import datetime
import sqlalchemy as db
from sqlalchemy import Table, Column, Integer, String, MetaData, DateTime, TEXT, ForeignKey, create_engine, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import select, func

SECTION_NAME = "database"
DB_CONFIG_FILE = "./database.ini"

class Database:

    metadata = MetaData()
    user_keys = Table("user_keys", metadata, 
        Column("id", Integer, primary_key=True),
        Column("account", String(25)),
        Column("created", DateTime(timezone=True), server_default=func.now()),
        Column("key_id", String(20), unique=True),
        Column("account_user", String(50)),
        Column("key_name", String(50)),
        Column("fingerprint", TEXT),
        Column("public_key", TEXT)
    )

    users = Table("users", metadata, 
        Column("id", Integer, primary_key=True),
        Column("user_id", String(25), unique=True, nullable=False),
        Column("auth_id", String(25), unique=True, nullable=False),
        Column("name", String(50), nullable=False),
        Column("account", String(25)),
        Column("created", DateTime(timezone=True), server_default=func.now()),
        Column("token_start",  DateTime(timezone=True)),
        Column("active_token", TEXT),
        Column("secret", TEXT),
        Column("active", Boolean),
        Column("tags", JSONB),
    )

    user_instances = Table("user_instances", metadata, 
        Column("id", Integer, primary_key=True),
        Column("account", String(25)),
        Column("created", DateTime(), nullable=False, server_default=func.now()),
        Column("instance_id", String(20), unique=True),
        Column("host", String(50)),
        Column("instance_type", String(20)),
        Column("instance_size", String(20)),
        Column("vm_image_metadata", JSONB),
        Column("account_user", String(50)),
        Column("attached_interfaces", JSONB),
        Column("attached_storage", JSONB),
        Column("key_name", String(50)),
        Column("assoc_firewall_rules", JSONB),
        Column("tags", JSONB)
    )

    guest_images = Table("guest_images", metadata,
        Column("id", Integer, primary_key=True),
        Column("account", String(20), nullable=True),
        Column("created", DateTime(), nullable=False, server_default=func.now()),
        Column("guest_image_id", String(20), unique=True),
        Column("guest_image_path", String(), nullable=False),
        Column("name", String()),
        Column("description", String()),
        Column("host", String(50)),
        Column("minimum_requirements", JSONB),
        Column("guest_image_metadata", JSONB),
        Column("tags", JSONB)
    )

    def __init__(self):
        self.engine = db.engine_from_config(self.get_connection_by_config(DB_CONFIG_FILE), prefix='db.')
        self.connection = self.engine.connect()
        self.metadata.create_all(self.engine)

    def get_connection_by_config(self, config_file_path):
        #TODO: Check if config file exists
        if(len(config_file_path) > 0 and len(SECTION_NAME) > 0):

            parser = ConfigParser()
            parser.read(config_file_path)
            if (parser.has_section(SECTION_NAME)):
                params = parser.items(SECTION_NAME)
                db_conn_dict = {}
                for param in params:
                    db_conn_dict[param[0]] = param[1]
                
            return db_conn_dict

        else:
            logging.error("Cannot make a database connection without config file path.")
    
    def insert(self, query, data):
        print("yes yes yes")
        result = self.connection.execute(query, data)
        return result
    
    def select(self, query, data):
        result = self.connection.execute(query, data).fetchall()
        return result
