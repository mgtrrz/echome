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
    host = models.ForeignKey(HostMachine, on_delete=models.CASCADE, to_field="host_id")
    instance_type = models.CharField(max_length=40)
    instance_size = models.CharField(max_length=40)
    path = models.CharField(max_length=200, null=True)
    metadata = models.JSONField(default=dict)
    image_metadata = models.JSONField()
    interfaces = models.JSONField()
    storage = models.JSONField()
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


class Volume(models.Model):
    volume_id = models.CharField(max_length=24, unique=True, db_index=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id")
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    host = models.ForeignKey(HostMachine, on_delete=models.CASCADE, to_field="host_id", null=True)
    virtual_machine = models.ForeignKey(VirtualMachine, on_delete=models.DO_NOTHING, to_field="instance_id", null=True)
    size = models.IntegerField(max_length=200)
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

    def generate_id(self):
        if self.instance_id is None or self.instance_id == "":
            self.instance_id = IdGenerator.generate("vol", 12)
        else:
            raise AttemptedOverrideOfImmutableIdException
    

    def populate_details(self):
        if not self.path:
            return False
        details = QemuImg().info(self.path)
        self.format = details["format"]
        self.size = details["virtual-size"]

    def __str__(self) -> str:
        return self.instance_id
