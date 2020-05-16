import logging
import os.path
import json
from database import Database
from sqlalchemy import select, and_
from vm_manager import vmManager
import subprocess

class GuestImage:

    imageType = "guest"

    def __init__(self):
        pass

    def registerImage(self, img_path, img_name, img_description, img_metadata, host="localhost"):
        db = Database()

        # Check to see if a file exists at that path
        if not os.path.exists(img_path):
            logging.error(f"File does not exist at specified file path: {img_path}")
            raise InvalidImagePath(f"File does not exist at specified file path: {img_path}")
            
        # Verify image type
        result = self.__run_command(["qemu-img", "info", img_path, "--output", "json"])
        obj = json.loads(result["output"])
        print(obj["format"])

        img_metadata["format"] = obj["format"]
        img_metadata["location"] = img_path
        img_metadata["actual-size"] = obj["actual-size"]
        img_metadata["virtual-size"] = obj["virtual-size"]

        stmt = db.guest_images.insert().values(
            guest_image_id=vmManager.generate_vm_id(type="gmi"), 
            name=img_name, 
            description=img_description, 
            host=host,
            minimum_requirements={},
            guest_image_metadata=img_metadata,
            tags={}
        )
        print(stmt)

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