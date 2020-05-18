import logging
import os.path
import json
from database import Database
from sqlalchemy import select, and_
from vm_manager import vmManager
import datetime
import subprocess

class GuestImage:

    imageType = "guest"

    def __init__(self):
        self.db = Database()
    
    def getAllImages(self):
        columns = [
            self.db.guest_images.c.created,
            self.db.guest_images.c.guest_image_path,
            self.db.guest_images.c.name,
            self.db.guest_images.c.description,
            self.db.guest_images.c.host,
            self.db.guest_images.c.minimum_requirements,
            self.db.guest_images.c.guest_image_metadata,
            self.db.guest_images.c.tags,
        ]
        select_stmt = select(columns)
        results = self.db.connection.execute(select_stmt).fetchall()
        if results:
            images = []
            image_meta = {}
            for row in results:
                print(row)
                i = 0
                for column in columns:
                    if column.name == "created":
                        print(type(row[i]))
                    
                    image_meta[column.name] = row[i]
                    i += 1
                images.append(image_meta)

            return {
                "success": True,
                "meta_data": images,
                "reason": "",
            }
        else:
            return {
                "success": False,
                "meta_data": {},
                "reason": "No images found",
            }

    
    def getImageMeta(self, img_id):

        columns = [
            self.db.guest_images.c.created,
            self.db.guest_images.c.guest_image_path,
            self.db.guest_images.c.name,
            self.db.guest_images.c.description,
            self.db.guest_images.c.host,
            self.db.guest_images.c.minimum_requirements,
            self.db.guest_images.c.guest_image_metadata,
            self.db.guest_images.c.tags,
        ]

        select_stmt = select(columns).where(
            self.db.guest_images.c.guest_image_id == img_id
        )
        results = self.db.connection.execute(select_stmt).fetchall()
        if results:
            image_meta = {}
            i = 0
            for column in columns:
                image_meta[column.name] = results[0][i]
                i += 1
            return {
                "success": True,
                "meta_data": image_meta,
                "reason": "",
            }
        else:
            return {
                "success": False,
                "meta_data": {},
                "reason": "No image with that image ID exists",
            }

    def registerImage(self, img_path, img_name, img_description, img_metadata={}, host="localhost"):

        # Check to see if a file exists at that path
        if not os.path.exists(img_path):
            logging.error(f"File does not exist at specified file path: {img_path}")
            raise InvalidImagePath(f"File does not exist at specified file path: {img_path}")
        
        # Check to make sure an image at the path already exists
        select_stmt = select(
            [self.db.guest_images.c.guest_image_id]
        ).where(
            and_(
                self.db.guest_images.c.guest_image_path == img_path
            )
        )
        results = self.db.connection.execute(select_stmt).fetchall()
        if results:
            logging.error(f"Image already exists in database. img_path={img_path}")
            return {
                "success": False,
                "meta_data": {
                    "img_path": img_path
                },
                "reason": "Image with that file path already exists.",
            }


        # Verify image type
        result = self.__run_command(["qemu-img", "info", img_path, "--output", "json"])
        obj = json.loads(result["output"])
        print(obj["format"])

        img_metadata["format"] = obj["format"]
        img_metadata["actual-size"] = obj["actual-size"]
        img_metadata["virtual-size"] = obj["virtual-size"]

        id = vmManager.generate_vm_id(type="gmi")

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
        result = self.db.connection.execute(stmt)
        if result:
            return {
                "success": True,
                "meta_data": {
                    "guest_image_id": id
                },
                "reason": "",
            }

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

class InvalidImagePath(Exception):
    pass