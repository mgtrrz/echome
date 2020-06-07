import time
from backend.id_gen import IdGenerator
from configparser import ConfigParser
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, MetaData, DateTime, TEXT, ForeignKey, create_engine, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import select, func
from sqlalchemy.ext.hybrid import hybrid_property
import sqlalchemy as db
import bcrypt
import secrets
import string

from .database import DbEngine


Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    metadata = MetaData()
    # A user can have multiple rows.
    # The primary row for a user will have a user_id, primary = true, and an empty auth_id.
    # This primary row will contain the username and password for auth login and general metainformation
    #
    # Any additional rows for a user will contain the primary user id in `related`, primary = false, and contain a unique auth_id. 
    # These are used for API keys.

    id = Column(Integer, primary_key=True)
    user_id = Column(String(25), unique=True, nullable=True)
    related = Column(String(25), unique=False, nullable=True)
    auth_id = Column(String(25), unique=True, nullable=True)
    primary = Column(Boolean)
    account = Column(String(25))
    username = Column(String(50), nullable=True)
    name = Column(String(50), nullable=True)
    created = Column(DateTime(timezone=True), server_default=func.now())
    token_start = Column(DateTime(timezone=True))
    active_token = Column(TEXT)
    secret = Column(TEXT)
    active = Column(Boolean, default=True)
    tags = Column(JSONB)

    def init_session(self):
        dbengine = DbEngine()
        self.session = dbengine.return_session()
        self.metadata.create_all(dbengine.engine)
        return self.session

    def commit(self):
        self.session.commit()

    def add(self):
        self.session.add(self)
        self.session.commit()

    def __str__(self):
        return self.username

    def get_user_id(self):
        return self.user_id
    
    def password(self):
        return self.secret

    # API credentials should be created off of the primary user account.
    # The method returns an exception if the User class primary flag is false
    def create_api_auth(self):
        if not id:
            return UserNotInstantiated("Current user class is not instantiated (No user information retrieved.)")
        
        if self.primary == False:
            return UserNotPrimary("Current user class is not the primary user.")

        secret_token = self.generate_token()

        return User(
            related=self.user_id,
            auth_id=IdGenerator.generate("auth"),
            primary=False,
            account=self.account,
            username=self.username,
            secret=self.set_password(secret_token, return_hash_secret=True)
        ), secret_token
    
    def generate_token(self, length=40):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for i in range(length))

    def set_password(self, plaintext, return_hash_secret=False):
        pwhash = bcrypt.hashpw(plaintext.encode('utf8'), bcrypt.gensalt())
        if return_hash_secret:
            return pwhash.decode('utf8')
        else:
            self.secret = pwhash.decode('utf8')

    def check_password(self, plaintext):
        return bcrypt.checkpw(plaintext.encode('utf8'), self.secret.encode('utf-8'))

class UserNotInstantiated(Exception):
    pass

class UserNotPrimary(Exception):
    pass