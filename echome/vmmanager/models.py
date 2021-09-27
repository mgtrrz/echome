import logging
from django.db import models
from echome.exceptions import AttemptedOverrideOfImmutableIdException
from echome.id_gen import IdGenerator

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
    metadata = models.JSONField(default=dict)
    image_metadata = models.JSONField()
    interfaces = models.JSONField()
    storage = models.JSONField()
    key_name = models.CharField(max_length=50)
    firewall_rules = models.JSONField(null=True)
    tags = models.JSONField(default=dict)

    def generate_id(self):
        if self.instance_id is None or self.instance_id == "":
            self.instance_id = IdGenerator.generate("vm")
        else:
            raise AttemptedOverrideOfImmutableIdException

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
