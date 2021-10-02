import logging
from django.db import models
from echome.id_gen import IdGenerator
from echome.exceptions import AttemptedOverrideOfImmutableIdException

logger = logging.getLogger(__name__)

# Create your models here.
class VirtualNetwork(models.Model):
    network_id = models.CharField(max_length=20, unique=True, db_index=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id")
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)

    name = models.CharField(max_length=40, null=False)
    class Type(models.TextChoices):
        BRIDGE_TO_LAN = 'BTL', 'BridgeToLan'
        NAT = 'NAT', 'NetworkAddressTranslation'

    type = models.CharField(
        max_length=4,
        choices=Type.choices,
        default=Type.BRIDGE_TO_LAN,
    )
    config = models.JSONField(default=dict)
    deactivated = models.BooleanField(default=False, null=False)
    tags = models.JSONField(default=dict)

    def generate_id(self):
        if self.network_id is None or self.network_id == "":
            self.network_id = IdGenerator.generate("vnet")
        else:
            raise AttemptedOverrideOfImmutableIdException

    def __str__(self) -> str:
        return self.network_id

