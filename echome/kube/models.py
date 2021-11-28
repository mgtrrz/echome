import logging
from django.db import models
from echome.id_gen import IdGenerator
from echome.exceptions import AttemptedOverrideOfImmutableIdException

logger = logging.getLogger(__name__)

class KubeCluster(models.Model):
    cluster_id = models.CharField(max_length=20, unique=True, db_index=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id", null=True)

    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    
    class Status(models.TextChoices):
        BUILDING = 1, 'Building'
        FAILED = 2, 'Failed'
        READY = 3, 'Ready'
        UPDATING = 4, 'Updating'
        DELETING = 5, 'Deleting'
        TERMINATED = 6, 'Terminated'

    status = models.CharField(
        max_length=4,
        choices=Status.choices,
        default=Status.BUILDING,
    )

    primary = models.ForeignKey("vmmanager.VirtualMachine", \
        on_delete=models.SET_NULL, \
        to_field="instance_id", \
        related_name='primary_controller', \
        null=True)
    associated_instances = models.ManyToManyField("vmmanager.VirtualMachine")

    minimum_requirements = models.JSONField(default=dict)
    image_metadata = models.JSONField(default=dict)
    deactivated = models.BooleanField(default=False)
    tags = models.JSONField(default=dict)

    def generate_id(self):
        if self.cluster_id is None or self.cluster_id == "":
            self.cluster_id = IdGenerator.generate("kube")
        else:
            raise AttemptedOverrideOfImmutableIdException
