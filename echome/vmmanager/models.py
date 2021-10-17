import logging
from django.db import models
from echome.exceptions import AttemptedOverrideOfImmutableIdException
from echome.id_gen import IdGenerator
from commander.qemuimg import QemuImg
from .instance_definitions import InstanceDefinition

logger = logging.getLogger(__name__)

class HostMachine(models.Model):
    host_id = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=40)
    ip = models.GenericIPAddressField()
    created = models.DateTimeField(auto_now_add=True, null=False)
    metadata = models.JSONField(default=dict)
    tags = models.JSONField(default=dict)

    def generate_id(self):
        if self.host_id is None or self.host_id == "":
            self.host_id = IdGenerator.generate("host")
        else:
            raise AttemptedOverrideOfImmutableIdException

    def get_cpu_model(self):
        if self.pk is None:
            logger.error("Attempted to get cpu info for HostMachine that does not have a row in database.")
            raise Exception
        
        return 

    def __str__(self) -> str:
        return self.name


class VirtualMachine(models.Model):
    instance_id = models.CharField(max_length=20, unique=True, db_index=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id")
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    host = models.ForeignKey(HostMachine, on_delete=models.CASCADE, to_field="host_id", null=True)
    instance_type = models.CharField(max_length=40)
    instance_size = models.CharField(max_length=40)
    path = models.CharField(max_length=200, null=True)
    metadata = models.JSONField(default=dict, null=True)
    image_metadata = models.JSONField(null=True)
    interfaces = models.JSONField(null=True)
    storage = models.JSONField(null=True)
    key_name = models.CharField(max_length=50)
    firewall_rules = models.JSONField(null=True)
    tags = models.JSONField(default=dict)

    class State(models.TextChoices):
        CREATING = 'CREATING', 'Creating'
        AVAILABLE = 'AVAILABLE', 'Available'
        TERMINATING = 'TERMINATING', 'Terminating'
        TERMINATED = 'TERMINATED', 'Terminated'
        ERROR = 'ERROR', 'Error'

    state = models.CharField(
        max_length=16,
        choices=State.choices,
        default=State.CREATING,
    )


    def generate_id(self):
        if self.instance_id is None or self.instance_id == "":
            self.instance_id = IdGenerator.generate("vm")
        else:
            raise AttemptedOverrideOfImmutableIdException


    def set_instance_definition(self, instance_def:InstanceDefinition):
        self.instance_type = instance_def.itype
        self.instance_size = instance_def.isize


    def __str__(self) -> str:
        return self.instance_id


class InstanceDefinition(models.Model):
    instance_definition_id = models.CharField(max_length=20, unique=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    host = models.ForeignKey(HostMachine, on_delete=models.CASCADE, to_field="host_id")
    instance_type = models.CharField(max_length=40)
    instance_size = models.CharField(max_length=40)
    cpu = models.CharField(max_length=40)
    memory = models.CharField(max_length=40)
    tags = models.JSONField(default=dict)

    def __str__(self) -> str:
        return self.instance_id


class OperatingSystem(models.TextChoices):
    WINDOWS = 'WINDOWS', 'Windows'
    LINUX = 'LINUX', 'Linux'
    OTHER = 'OTHER', 'Other'
    NONE = 'NONE', 'None'

# All images (disk images) derive from this model.
# There's currently only two types:
# GuestImage (gmi-): For ALL accounts/users on the server
# UserImage (vmi-): For only a specific account on the server
class Image(models.Model):
    class ImageType(models.TextChoices):
        GUEST = 'GUEST', 'Guest'
        USER = 'USER', 'User'

    image_type = models.CharField(
        max_length=16,
        choices=ImageType.choices,
        default=ImageType.GUEST,
    )
    image_id = models.CharField(max_length=20, unique=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id", null=True)
    image_path = models.CharField(max_length=200)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=100)

    minimum_requirements = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)
    deactivated = models.BooleanField(default=False)
    tags = models.JSONField(default=dict)

    class State(models.TextChoices):
        CREATING = 'CREATING', 'Creating'
        AVAILABLE = 'AVAILABLE', 'Available'
        ERROR = 'ERROR', 'Error'
        DELETING = 'DELETING', 'Deleting'
        DELETED = 'DELETED', 'Deleted'

    state = models.CharField(
        max_length=16,
        choices=State.choices,
        default=State.CREATING,
    )

    operating_system = models.CharField(
        max_length=12,
        choices=OperatingSystem.choices,
        default=OperatingSystem.LINUX,
    )
    

    @property
    def format(self):
        """Helper property for retrieving the format from the image metadata."""
        return self.metadata["format"]


    @property
    def is_ready_for_use(self) -> bool:
        """Helper property to determine if the image can be used in a VM."""
        return True if self.state == Image.State.AVAILABLE and self.deactivated is False else False


    def generate_id(self):
        if self.image_id is None or self.image_id == "":
            if self.image_type == Image.ImageType.GUEST:
                id = "gmi"
            elif self.image_type == Image.ImageType.USER:
                id = "vmi"

            self.image_id = IdGenerator.generate(id)
            logger.debug(f"Generated ID: '{self.image_id}'")
        else:
            raise AttemptedOverrideOfImmutableIdException


    def set_image_metadata(self):
        obj = QemuImg().info(self.image_path)
        logger.debug(obj)

        self.metadata = {
            "format": obj["format"],
            "actual-size": obj["actual-size"],
            "virtual-size": obj["virtual-size"]
        }


    def __str__(self) -> str:
        return self.image_id


class Volume(models.Model):
    volume_id = models.CharField(max_length=24, unique=True, db_index=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id")
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    host = models.ForeignKey(HostMachine, on_delete=models.CASCADE, to_field="host_id", null=True)
    virtual_machine = models.ForeignKey(VirtualMachine, on_delete=models.SET_NULL, to_field="instance_id", null=True)
    size = models.BigIntegerField(null=True)
    parent_image = models.CharField(max_length=60, null=True)
    format = models.CharField(max_length=12, null=True)
    metadata = models.JSONField(default=dict)
    path = models.CharField(max_length=200)
    tags = models.JSONField(default=dict)

    class State(models.TextChoices):
        CREATING = 'CREATING', 'Creating'
        AVAILABLE = 'AVAILABLE', 'Available'
        IN_USE = 'IN_USE', 'In Use'
        ATTACHED = 'ATTACHED', 'Attached'
        DELETING = 'DELETING', 'Deleting'
        DELETED = 'DELETED', 'Deleted'
        ERROR = 'ERROR', 'Error'

    state = models.CharField(
        max_length=16,
        choices=State.choices,
        default=State.CREATING,
    )

    operating_system = models.CharField(
        max_length=12,
        choices=OperatingSystem.choices,
        default=OperatingSystem.LINUX,
        null=True
    )


    def generate_id(self):
        if self.volume_id is None or self.volume_id == "":
            self.volume_id = IdGenerator.generate("vol", 12)
        else:
            raise AttemptedOverrideOfImmutableIdException
    

    def populate_metadata(self):
        if not self.path:
            return False
        details = QemuImg().info(self.path)
        self.format = details["format"]
        self.size = details["virtual-size"]


    def new_volume_from_image(self, image:Image):
        self.parent_image = image.image_id
        self.format = image.metadata["format"]
        self.operating_system = image.operating_system


    def __str__(self) -> str:
        return self.instance_id
