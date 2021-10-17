import logging
import os
import shutil
from pathlib import Path
from identity.models import User
from .models import Image
from .exceptions import (
    ImageAlreadyExistsError, 
    InvalidImagePath, 
    ImageDoesNotExistError, 
    ImagePrepError, 
    ImageCopyError
)


logger = logging.getLogger(__name__)

class ImageManager:

    image:Image = None

    def __init__(self, image_id:str = None) -> None: 
        if image_id:
            self.image = self.__get_image_from_id(image_id)


    def register_guest_image(self, path:str, name:str, description:str, host="localhost", tags=None):
        """Instantly register an image for use. If you need to prepare an image that needs processing done
        in the background, use prepare_guest_image()."""

        self.prepare_guest_image()
        return self._register_image(path, name, description, host=host, tags=tags)


    def register_user_image(self, path:str, name:str, description:str, user:User, host="localhost", tags=None):
        """Instantly register a user image for use. If you need to prepare an image that needs processing done
        in the background, use prepare_user_image()."""

        self.prepare_user_image(user)
        return self._register_image(path, name, description, host=host, tags=tags)

    
    def prepare_guest_image(self) -> str:
        """Prepare a Guest image by instantiating an empty object with an ID which can then be later registered.
        Complete the image with finish_guest_image().

        This will create a relatively empty value in the database with the state set to 'CREATING'.

        Returns the Image ID but the image can be accessed with obj.image
        """

        self.image = Image(
            image_type =  Image.ImageType.GUEST,
        )
        self.image.generate_id()
        self.image.save()
        return self.image.image_id
    

    def finish_guest_image(self, path, name, description, tags:dict = None) -> str:
        """Finishes a guest image that was first prepared."""
        if not self.image:
            logger.warn("Cannot finish an image that was not first prepared")
            raise ImagePrepError
        
        return self._register_image(path, name, description, tags)


    def prepare_user_image(self, user:User, name:str, description:str, tags:dict = None) -> str:
        """Prepare a User image by instantiating an empty object with an ID which can then be later registered.
        Complete the image with finish_user_image().

        This will create a relatively empty value in the database with the state set to 'CREATING'.

        Returns the Image ID but the image can be accessed with obj.image
        """

        self.image = Image(
            image_type = Image.ImageType.USER,
            account = user.account,
            name = name,
            description = description,
            tags = tags if tags else {}
        )

        self.image.generate_id()
        self.image.save()
        return self.image.image_id
    

    def finish_user_image(self, path) -> str:
        """Finishes a user image that was first prepared with prepare_user_image()."""
        if not self.image:
            logger.warn("Cannot finish an image that was not first prepared")
            raise ImagePrepError
        
        return self._register_image(path)


    def _register_image(self, path:str):
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

        self.image.state = Image.State.AVAILABLE

        self.image.save()
        return self.image.image_id


    def get_image_from_id(self, image_id:str, user:User = None) -> Image:
        """Returns an image object from an image_id string belonging to an account."""
        
        image = None
        try:
            if image_id.startswith("vmi-"):
                image:Image = Image.objects.get(
                    image_type=Image.ImageType.USER,
                    image_id=image_id,
                    deactivated=False,
                    account=user.account
                )
            elif image_id.startswith("gmi-"):
                image:Image = Image.objects.get(
                    image_type=Image.ImageType.GUEST,
                    image_id=image_id,
                    deactivated=False,
                )
            else:
                raise Image.DoesNotExist
        except Image.DoesNotExist:
            logger.debug(f"Did not find defined image with ID: {image_id}")
            raise ImageDoesNotExistError()
        
        return image


    def copy_image(self, image:Image, destination_dir:Path, file_name:str) -> str:
        """Copy a guest or user image to the path. Returns the full path of the copied image."""
        img_path = image.image_path
        img_format = image.format

        # Form the path of the final image
        destination_vm_img = destination_dir.absolute() / f"{file_name}.{img_format}"

        try:
            logger.debug(f"Copying image: {img_path} TO directory {destination_dir} as {destination_vm_img}")
            shutil.copy2(img_path, destination_vm_img)
        except FileNotFoundError:
            raise ImageCopyError("Encountered an error on image copy. Original image is not found. Cannot continue.")
        except OSError as e:
            raise ImageCopyError(f"Encountered other error during image copy. {e}")

        logger.debug(f"Final image: {destination_vm_img}")
        return destination_vm_img


    def deactivate_image(self):
        pass


    def delete_image(self):
        pass

    
    def __get_image_from_id(self, image_id:str) -> Image:
        """Returns an image object from an image_id string belonging to an account, bypassing all
        normal filters such as deactivated or user account."""
        try:
            return Image.objects.get(
                    image_id=image_id,
                )
        except Image.DoesNotExist:
            logger.debug(f"Did not find defined image with ID: {image_id}")
            raise ImageDoesNotExistError()
        
