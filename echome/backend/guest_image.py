import logging
import os.path
import json
import datetime
import subprocess
from sqlalchemy import select, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Table, Column, Integer, String, \
    MetaData, DateTime, TEXT, ForeignKey, create_engine, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import select, func
from .id_gen import IdGenerator
from .database import dbengine
from .user import User
from .commander import QemuImg

Base = declarative_base()

class BaseImage(Base):
    imageType = None
    __tablename__ = "guest_images"

    id = Column(Integer, primary_key=True)
    account = Column(String(20), nullable=True)
    created = Column(DateTime(), nullable=False, server_default=func.now())
    guest_image_id = Column(String(20), unique=True)
    guest_image_path = Column(String(), nullable=False)
    name = Column(String())
    description = Column(String())
    host = Column(String(50))
    minimum_requirements = Column(JSONB)
    guest_image_metadata = Column(JSONB)
    deactivated = Column(Boolean, default=False)
    tags = Column(JSONB)

    def init_session(self):
        self.session = dbengine.return_session()
        return self.session

    def commit(self):
        self.session.commit()

    def add(self):
        self.session.add(self)
        self.session.commit()

    def __str__(self):
        return self.name


class GuestImage(BaseImage):
    imageType = "guest"
    __tablename__ = "guest_images"

class UserImage(BaseImage):
    imageType = "user"
    __tablename__ = "guest_images"



class ImageManager:
    def getAllImages(self, type:str, user:User=None):
        if type == "guest":
            res = dbengine.session.query(GuestImage).filter_by(
                account=None
            ).all()
        elif type == "user":
            res = dbengine.session.query(UserImage).filter_by(
                account=user.account
            ).all()
        else:
            return None

        return res
    
    def getImage(self, img_type, img_id, user:User=None):
        if img_type == "guest":
            account = None
            img = GuestImage
        elif img_type == "user":
            account = user.account
            img = UserImage
        else:
            return False
        
        results = dbengine.session.query(img).filter_by(
            guest_image_id=img_id,
            account=account,
        ).first()

        if not results:
            raise InvalidImageId
            
        return results


    def registerImage(self, img_type, img_path, img_name, img_description, img_user, user:User=None, img_metadata={}, host="localhost", tags={}):

        # Check to see if a file exists at that path
        if not os.path.exists(img_path):
            logging.error(f"File does not exist at specified file path: {img_path}")
            raise InvalidImagePath(f"File does not exist at specified file path: {img_path}")

        if img_type == "guest":
            id = IdGenerator.generate(type="gmi")
            account = None
            img = GuestImage
        elif img_type == "user":
            id = IdGenerator.generate(type="vmi")
            account = user.account
            img = UserImage
        else:
            return False
        
        # Check to make sure an image at the path already exists
        results = dbengine.session.query(img).filter_by(
            guest_image_path=img_path
        ).all()

        if results:
            logging.error(f"Image already exists in database. img_path={img_path}")
            raise InvalidImageAlreadyExists(f"Image already exists in database. img_path={img_path}")


        # Verify image type
        obj = QemuImg().info(img_path)
        print(obj["format"])

        img_metadata["user"] = img_user
        img_metadata["format"] = obj["format"]
        img_metadata["actual-size"] = obj["actual-size"]
        img_metadata["virtual-size"] = obj["virtual-size"]


        new_img = img(
            account = account,
            guest_image_id=id,
            guest_image_path=img_path,
            name=img_name,
            description=img_description,
            host=host,
            minimum_requirements={},
            guest_image_metadata=img_metadata,
            tags=tags
        )

        new_img.add()
        return id

    def __str__(self):
        return
    


class InvalidImageId(Exception):
    pass

class InvalidImagePath(Exception):
    pass

class InvalidImageAlreadyExists(Exception):
    pass

class UserImageInvalidUser(Exception):
    pass