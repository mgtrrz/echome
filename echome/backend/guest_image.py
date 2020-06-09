import logging
import os.path
import json
import datetime
import subprocess
from sqlalchemy import select, and_
from .id_gen import IdGenerator
from .database import Database

class GuestImage:

    imageType = "guest"

    def __init__(self, user=None):
        self.db = Database()
        if self.imageType == "user":
            if not user:
                raise UserImageInvalidUser("User object required when calling UserImage class")
            self.user = user
    
    def getAllImages(self):
        columns = [
            self.db.guest_images.c.created,
            self.db.guest_images.c.account,
            self.db.guest_images.c.guest_image_id,
            self.db.guest_images.c.guest_image_path,
            self.db.guest_images.c.name,
            self.db.guest_images.c.description,
            self.db.guest_images.c.host,
            self.db.guest_images.c.minimum_requirements,
            self.db.guest_images.c.guest_image_metadata,
            self.db.guest_images.c.tags,
        ]

        if self.imageType == "guest":
            select_stmt = select(columns)
        elif self.imageType == "user":
            select_stmt = select(columns).where(
                self.db.guest_images.c.account == self.user["account_id"]
            )
        
        results = self.db.connection.execute(select_stmt).fetchall()
        if results:
            images = []
            for row in results:
                image_meta = {}
                i = 0
                for column in columns:
                    if column.name == "created":
                        image_meta[column.name] = str(row[i])
                    else:
                        image_meta[column.name] = row[i]
                    i += 1
                images.append(image_meta)

            return images
        else:
            return None

    
    def getImageMeta(self, img_id):

        columns = [
            self.db.guest_images.c.created,
            self.db.guest_images.c.account,
            self.db.guest_images.c.guest_image_id,
            self.db.guest_images.c.guest_image_path,
            self.db.guest_images.c.name,
            self.db.guest_images.c.description,
            self.db.guest_images.c.host,
            self.db.guest_images.c.minimum_requirements,
            self.db.guest_images.c.guest_image_metadata,
            self.db.guest_images.c.tags,
        ]

        if self.imageType == "guest":
            select_stmt = select(columns).where(
                self.db.guest_images.c.guest_image_id == img_id
            )
        elif self.imageType == "user":
            select_stmt = select(columns).where(
                and_(
                    self.db.guest_images.c.account == self.user["account_id"],
                    self.db.guest_images.c.guest_image_id == img_id
                )
            )


        results = self.db.connection.execute(select_stmt).fetchall()
        images = []
        if results:
            image_meta = {}
            i = 0
            for column in columns:
                if column.name == "guest_image_metadata":
                    image_meta[column.name] = results[0][i]
                else:
                    image_meta[column.name] = str(results[0][i])
                i += 1
            images.append(image_meta)
        else:
            logging.error(f"Image with that ID does not exist: {img_id}")
            raise InvalidImageId(f"Image with that ID does not exist: {img_id}")
        
        return images


    def registerImage(self, img_path, img_name, img_description, img_metadata={}, host="localhost"):

        # Check to see if a file exists at that path
        if not os.path.exists(img_path):
            logging.error(f"File does not exist at specified file path: {img_path}")
            raise InvalidImagePath(f"File does not exist at specified file path: {img_path}")
        
        # Check to make sure an image at the path already exists
        select_stmt = select(
            [self.db.guest_images.c.guest_image_id]
        ).where(self.db.guest_images.c.guest_image_path == img_path)

        results = self.db.connection.execute(select_stmt).fetchall()
        if results:
            logging.error(f"Image already exists in database. img_path={img_path}")
            raise InvalidImageAlreadyExists(f"Image already exists in database. img_path={img_path}")


        # Verify image type
        result = self.__run_command(["qemu-img", "info", img_path, "--output", "json"])
        obj = json.loads(result["output"])
        print(obj["format"])

        img_metadata["format"] = obj["format"]
        img_metadata["actual-size"] = obj["actual-size"]
        img_metadata["virtual-size"] = obj["virtual-size"]

        id = IdGenerator.generate(type="gmi")

        if self.imageType == "guest":
            stmt = self.db.guest_images.insert().values(
                guest_image_id=id, 
                guest_image_path=img_path,
                name=img_name, 
                description=img_description, 
                host=host,
                minimum_requirements={},
                guest_image_metadata=img_metadata,
                tags={}
            )
        elif self.imageType == "user":
            stmt = self.db.guest_images.insert().values(
                account=self.user["account_id"],
                guest_image_id=id, 
                guest_image_path=img_path,
                name=img_name, 
                description=img_description, 
                host=host,
                minimum_requirements={},
                guest_image_metadata=img_metadata,
                tags={}
            )
        
        result = self.db.connection.execute(stmt)
        if result:
            return id

    def __str__(self):
        return
    
    def __run_command(self, cmd: list):
        logging.debug("Running command: ")
        logging.debug(cmd)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
        output = ""
        for line in process.stdout:
            output = output + line

        #logging.debug(output.strip())
        return_code = process.poll()
        logging.debug(f"SUBPROCESS RETURN CODE: {return_code}")
        return {
            "return_code": return_code,
            "output": output,
        }

class UserImage(GuestImage):
    imageType = "user"
    pass

class InvalidImageId(Exception):
    pass

class InvalidImagePath(Exception):
    pass

class InvalidImageAlreadyExists(Exception):
    pass

class UserImageInvalidUser(Exception):
    pass