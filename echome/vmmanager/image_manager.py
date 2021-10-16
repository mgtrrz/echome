import logging
import os
from identity.models import User
from .exceptions import ImageAlreadyExistsError, InvalidImagePath
from .models import Image

logger = logging.getLogger(__name__)

class ImageManager:

    image:Image = None

    def register_guest_image(self, path:str, name:str, description:str, user:User=None, host="localhost", tags=None):
        """Instantly register an image for use. If you need to prepare an image that needs processing done
        in the background, use prepare_guest_image()."""

        self.prepare_guest_image()
        self._register_image(path, name, description, user, host, tags)


    
    def prepare_guest_image(self) -> str:
        """Prepare a Guest image by instantiating an empty object with an ID which can then be later registered.
        Returns the Image ID but the image can be accessed with obj.image"""

        self.image = Image(
            type =  Image.ImageType.GUEST,
        )
        self.image.generate_id()
        return self.image.image_id


    def _register_image(self, path:str, name:str, description:str, user:User=None, host="localhost", tags=None):
        # Check to see if a file exists at the provided path
        if not os.path.exists(path):
            logger.error(f"File does not exist at specified file path: {path}")
            raise InvalidImagePath(f"File does not exist at specified file path: {path}")
        
        # Check to see if an image at the path already exists
        if Image.objects.filter(image_path=path).exists():
            logger.error(f"Image already exists in database. img_path={path}")
            raise ImageAlreadyExistsError(f"Image already exists in database. img_path={path}")
        
        self.image.image_path = path
        self.image.set_image_metadata()

        if self.image_type == Image.ImageType.USER:
            self.image.account = user.account
        
        self.name = name
        self.description = description

        self.image.state = Image.State.READY

        if tags:
            self.image.tags 

        self.image.save()
        return self.image.image_id


    def deactivate_image(self):
        pass


    def delete_image(self):
        pass
