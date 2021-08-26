from django.db import models

class Account(models.Model):
    account_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=40)
    created = models.DateTimeField(auto_now_add=True, null=False)
    secret = models.TextField()
    tags = models.JSONField()

    def __str__(self) -> str:
        return self.account_id


class User(models.Model):
    user_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=40)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_login = models.DateTimeField(auto_now=False, null=True)
    active = models.BooleanField(default=True)
    secret = models.TextField()
    tags = models.JSONField()

    def __str__(self) -> str:
        return self.user_id


class UserAccessAccounts(models.Model):
    auth_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=40)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True, null=False)
    last_login = models.DateTimeField(auto_now=False, null=True)
    active = models.BooleanField(default=True)
    secret = models.TextField()
    tags = models.JSONField()

    def __str__(self) -> str:
        return self.auth_id


class ServerServiceAccounts(models.Model):
    sa_id = models.CharField(max_length=20, unique=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    owner = models.CharField(max_length=40)
    created = models.DateTimeField(auto_now_add=True, null=False)
    active = models.BooleanField(default=True)
    secret = models.TextField()
    tags = models.JSONField()

    def __str__(self) -> str:
        return self.sa_id