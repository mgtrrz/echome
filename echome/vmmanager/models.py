from django.db import models

class HostMachines(models.Model):
    host_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=40)
    ip = models.GenericIPAddressField()
    created = models.DateTimeField(auto_now_add=True, null=False)
    location = models.CharField(max_length=40)
    tags = models.JSONField(null=True)

    def __str__(self) -> str:
        return self.name

class UserKeys(models.Model):
    key_id = models.CharField(max_length=20, unique=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=50)
    service_key = models.BooleanField(default=False)
    service_owner = models.CharField(max_length=40, null=True)
    fingerprint = models.TextField()
    public_key = models.TextField()
    tags = models.JSONField(null=True)

    def __str__(self) -> str:
        return self.name

class VirtualMachines(models.Model):
    instance_id = models.CharField(max_length=20, unique=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    host = models.ForeignKey(HostMachines, on_delete=models.CASCADE)
    instance_type = models.CharField(max_length=40)
    instance_size = models.CharField(max_length=40)
    image_metadata = models.JSONField()
    interfaces = models.JSONField()
    storage = models.JSONField()
    key_name = models.CharField(max_length=50)
    firewall_rules = models.JSONField(null=True)
    tags = models.JSONField(null=True)

    def __str__(self) -> str:
        return self.instance_id