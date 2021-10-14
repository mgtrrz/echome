import logging
import os
from identity.models import User
from .exceptions import InvalidImageAlreadyExists, InvalidImagePath
from .models import Image

logger = logging.getLogger(__name__)

class ImageManager:

    def register_guest_image(self, path:str, name:str, description:str, user:User=None, host="localhost", tags=None):
        pass

    def _register_image(self, path:str, name:str, description:str, user:User=None, host="localhost", tags=None):
        # Check to see if a file exists at the provided path
        if not os.path.exists(path):
            logger.error(f"File does not exist at specified file path: {path}")
            raise InvalidImagePath(f"File does not exist at specified file path: {path}")
        
        # Check to see if an image at the path already exists
        if Image.objects.filter(image_path=path).exists():
            logger.error(f"Image already exists in database. img_path={path}")
            raise InvalidImageAlreadyExists(f"Image already exists in database. img_path={path}")
        
        new_image = Image(
            name=name,
            description=description,
        )
        new_image.generate_id()
        
        new_image.set_image_metadata()

        if self.image_type == Image.ImageType.USER:
            self.account = user.account
        
        self.image_path = path
        self.name = name
        self.description = description
        #self.minimum_requirements = dict
        if tags:
            self.tags 
        self.save()
        return self.image_id

