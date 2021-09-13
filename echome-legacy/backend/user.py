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
import jwt
import re

from .database import dbengine

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
    server_secret = Column(TEXT)
    active = Column(Boolean, default=True)
    tags = Column(JSONB)

    # def init_session(self):
    #     self.session = dbengine.return_session()
    #     return self.session

    # def commit(self):
    #     self.session.commit()

    # def add(self):
    #     self.session.add(self)
    #     self.session.commit()

    def __str__(self):
        return self.username if self.username is not None else self.user_id

    def get_user_id(self):
        return self.user_id
    
    def password(self):
        return self.secret
    
    # Server-side secret for JWT signing.
    # More useful for API tokens
    def set_server_secret(self):
        self.server_secret = self.generate_token(length=60)

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
            secret=self.set_password(secret_token, return_hash_secret=True),
            server_secret=self.generate_token(length=60)
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
    
    def is_service_account(self):
        if re.match(r"svc-", self.user_id):
            return True
        else:
            return False

    
class UserManager():

    def get_user(self, user_id_or_username:str=None, auth_id:str=None, account:str=None):
        if auth_id:
            return dbengine.session.query(User).filter_by(
                auth_id=auth_id
            ).first()
        elif user_id_or_username:
            if re.match(r"user-", user_id_or_username):
                if account:
                    return dbengine.session.query(User).filter_by(
                        user_id=user_id_or_username,
                        account=account
                    ).first()
                else:
                    return dbengine.session.query(User).filter_by(
                        user_id=user_id_or_username
                    ).first()
            else:
                if account:
                    return dbengine.session.query(User).filter_by(
                        account=account,
                        username=user_id_or_username
                    ).first()
                else:
                    return dbengine.session.query(User).filter_by(
                        username=user_id_or_username
                    ).first()
        else:
            return False
    
    def get_user_aliases(self, user:User):
        return dbengine.session.query(User).filter(
                User.related == user.user_id,
                User.account == user.account,
            ).all()

    def get_all_users(self, account:str, get_aliases=False):
        results = dbengine.session.query(User).filter(
                User.account == account,
                User.user_id != None,
            ).all()
        users = []
        for user in results:
            if user.is_service_account() is False:
                users.append(user)
        
        return users

    def create_user(self, account:str, username:str, name:str, tags:dict, password:str=None):
        newUser = User(
            user_id=IdGenerator.generate("user"),
            primary=True,
            account=account,
            username=username,
            name=name,
        )

        user_info = {}
        user_info['user_id'] = newUser.user_id
        user_info['user_name'] = username

        if not password:
            # Set rand password
            user_info['password'] = secrets.token_urlsafe(12)
            password = user_info['password']

        newUser.set_password(password)
        dbengine.session.add(newUser)
        dbengine.session.commit()

        return user_info

class ServiceAccountManager():
    def create_service_account(self, account:str):
        user = User()
        secret_token = user.generate_token()

        svc_acct = User(
            user_id=IdGenerator.generate("svc"),
            auth_id=IdGenerator.generate("auth"),
            secret=user.set_password(secret_token, return_hash_secret=True),
            server_secret=user.generate_token(length=60),
            primary=True,
            account=account,
        )

        dbengine.session.add(svc_acct)
        dbengine.session.commit()
        return svc_acct.auth_id, secret_token
    
    def get_service_account(self, auth_id:str=None):
        user = dbengine.session.query(User).filter_by(
                auth_id=auth_id
            ).first()

        if user is not None and user.is_service_account():
            return user

        return False  

class UserNotInstantiated(Exception):
    pass

class UserNotPrimary(Exception):
    pass