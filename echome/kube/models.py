import logging
from django.db import models
from identity.models import User
from echome.id_gen import IdGenerator
from echome.exceptions import AttemptedOverrideOfImmutableIdException

logger = logging.getLogger(__name__)

class KubeDbManager(models.Manager):
    def get_cluster_with_id_or_name(self, user:User, cluster_identifier:str):
        pass

class KubeCluster(models.Model):
    cluster_id = models.CharField(max_length=20, unique=True, db_index=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id", null=True)
    name = models.CharField(max_length=30, null=True, unique=False)
    created = models.DateTimeField(auto_now_add=True, null=False)
    version = models.CharField(max_length=8, unique=False, null=True)
    last_modified = models.DateTimeField(auto_now=True)
    
    class Status(models.TextChoices):
        BUILDING = 'BUILDING', 'Building'
        FAILED = 'FAILED', 'Failed'
        READY = 'READY', 'Ready'
        UPDATING = 'UPDATING', 'Updating'
        DELETING = 'DELETING', 'Deleting'
        TERMINATED = 'TERMINATED', 'Terminated'

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.BUILDING,
    )

    primary = models.ForeignKey("vmmanager.VirtualMachine", \
        on_delete=models.SET_NULL, \
        to_field="instance_id", \
        related_name='primary_controller', \
        null=True)
    associated_instances = models.ManyToManyField("vmmanager.VirtualMachine")

    metadata = models.JSONField(default=dict)
    deactivated = models.BooleanField(default=False)
    tags = models.JSONField(default=dict)

    objects = KubeDbManager()

    def generate_id(self):
        if self.cluster_id is None or self.cluster_id == "":
            self.cluster_id = IdGenerator.generate("kube")
        else:
            raise AttemptedOverrideOfImmutableIdException
