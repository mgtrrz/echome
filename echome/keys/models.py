import logging
from django.db import models
from echome.exceptions import AttemptedOverrideOfImmutableIdException
from echome.id_gen import IdGenerator

logger = logging.getLogger(__name__)

class UserKey(models.Model):
    key_id = models.CharField(max_length=20, unique=True, db_index=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id")
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=50)
    service_key = models.BooleanField(default=False)
    service_owner = models.CharField(max_length=40, null=True)
    fingerprint = models.TextField()
    public_key = models.TextField()
    tags = models.JSONField(default=dict)

    def generate_id(self):
        if self.key_id is None or self.key_id == "":
            self.key_id = IdGenerator.generate("key")
        else:
            raise AttemptedOverrideOfImmutableIdException

    def __str__(self) -> str:
        return self.key_id

