import os
import logging
from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from identity.models import User
from echome.id_gen import IdGenerator
from echome.commander import QemuImg
from echome.exceptions import AttemptedOverrideOfImmutableIdException

logger = logging.getLogger(__name__)

# All images (disk images) derive from this model.
# There's currently only two types:
# GuestImage (gmi-): For ALL accounts/users on the server
# UserImage (vmi-): For only a specific account on the server
class BaseImageModel(models.Model):
    image_type = None
    image_id = models.CharField(max_length=20, unique=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    
    image_path = models.CharField(max_length=200)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=100)
    #host = models.ForeignKey("vmmanager.HostMachines", on_delete=models.CASCADE, to_field="host_id")

    minimum_requirements = models.JSONField(default=dict)
    image_metadata = models.JSONField(default=dict)
    deactivated = models.BooleanField(default=False)
    tags = models.JSONField(default=dict)

    class Meta:
        abstract = True

    def generate_id(self):
        if self.image_id is None or self.image_id == "":
            if self.image_type == "guest":
                id = "gmi"
            elif self.image_type == "user":
                id = "vmi"
            else:
                raise Exception("Unknown image type provided")
            self.image_id = IdGenerator.generate(id)
            logger.debug(f"Generated ID: '{self.image_id}'")
        else:
            raise AttemptedOverrideOfImmutableIdException

    def register_image(self, path:str, name:str, description:str, user:User=None, host="localhost", tags=None):
        # Check to see if a file exists at the provided path
        if not os.path.exists(path):
            logger.error(f"File does not exist at specified file path: {path}")
            raise InvalidImagePath(f"File does not exist at specified file path: {path}")

        self.generate_id()
        
        # Check to see if an image at the path already exists
        if self.image_type == "guest":
            cl = GuestImage
        elif self.image_type == "user":
            cl = UserImage
        else:
            logger.exception("Image type is something other than guest or user?")
            raise
        
        if cl.objects.filter(image_path=path).exists():
            logger.error(f"Image already exists in database. img_path={path}")
            raise InvalidImageAlreadyExists(f"Image already exists in database. img_path={path}")


        # Verify image type
        obj = QemuImg().info(path)
        print(obj["format"])

        img_metadata = {}
        img_metadata["format"] = obj["format"]
        img_metadata["actual-size"] = obj["actual-size"]
        img_metadata["virtual-size"] = obj["virtual-size"]

        if self.image_type == "user":
            self.account = user.account
        
        self.image_path = path
        self.name = name
        self.description = description
        #self.minimum_requirements = dict
        self.image_metadata = img_metadata
        if tags:
            self.tags
        self.save()
        return self.image_id

    def __str__(self) -> str:
        return self.image_id

class GuestImage(BaseImageModel):
    image_type = "guest"
    def __str__(self) -> str:
        return self.image_id
    

class UserImage(BaseImageModel):
    image_type = "user"
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id", null=True)

    def __str__(self) -> str:
        return self.image_id

class InvalidImageId(Exception):
    pass

class InvalidImagePath(Exception):
    pass

class InvalidImageAlreadyExists(Exception):
    pass

class UserImageInvalidUser(Exception):
    pass