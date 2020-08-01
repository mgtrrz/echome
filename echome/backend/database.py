import logging
from backend.config import ecHomeConfig
from datetime import datetime
import sqlalchemy as db
#from uwsgidecorators import postfork
from sqlalchemy import Table, Column, Integer, String, MetaData, DateTime, TEXT, ForeignKey, create_engine, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import select, func
from sqlalchemy.orm import sessionmaker

SECTION_NAME = "database"
DB_CONFIG_FILE = "/etc/echome/database.ini"


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

    accounts = Table("accounts", metadata, 
        Column("id", Integer, primary_key=True),
        Column("account", String(25), unique=True, nullable=False),
        Column("account_name", String(25), unique=True, nullable=False),
        Column("primary_user_id", String(50), nullable=False),
        Column("name", String(50), nullable=False),
        Column("created", DateTime(timezone=True), server_default=func.now()),
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
        logging.debug("Opening Postgres Engine connection..")
        self.engine = db.create_engine(ecHomeConfig.Database().url)
        self.connection = self.engine.connect()
        self.metadata.create_all(self.engine)
    
    def insert(self, query, data):
        print("yes yes yes")
        result = self.connection.execute(query, data)
        return result
    
    def select(self, query, data):
        result = self.connection.execute(query, data).fetchall()
        return result
    
    # @postfork
    # def engine_dispose(self):
    #     logging.debug("Class Database: ENGINE DISPOSE called!")
    #     self.engine.dispose()

class DbEngine:
    metadata = MetaData()

    session = None

    def __init__(self):
        logging.debug("Opening Postgres Engine connection..")
        self.engine = db.create_engine(ecHomeConfig.Database().url)
        self.connection = self.engine.connect()
        self.set_session()

    def return_session(self):
        return self.session
    
    def set_session(self):
        maker = sessionmaker(bind=self.engine)
        self.session = maker()
    
    def create_tables(self):
        self.metadata.create_all(self.engine)
    
    # @postfork
    # def engine_dispose(self):
    #     logging.debug("Class Database: ENGINE DISPOSE called!")
    #     self.engine.dispose()


dbengine = DbEngine()
