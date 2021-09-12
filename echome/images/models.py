from django.db import models

class BaseImageModel(models.Model):
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

    def __str__(self) -> str:
        return self.image_id

class GuestImage(BaseImageModel):
    def __str__(self) -> str:
        return self.image_id
    

class UserImage(BaseImageModel):
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id", null=True)

    def __str__(self) -> str:
        return self.image_id
