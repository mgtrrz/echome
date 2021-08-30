from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from echome.id_gen import IdGenerator
import string
import secrets

class AttemptedOverrideOfImmutableIdException(Exception):
    pass

class AccountNotFound(Exception):
    pass

class Account(models.Model):
    account_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=40)
    created = models.DateTimeField(auto_now_add=True, null=False)
    secret = models.TextField(null=True)
    tags = models.JSONField(default=dict)

    def __str__(self) -> str:
        return self.account_id
    
    def generate_id(self):
        if self.account_id is None:
            self.account_id = IdGenerator.generate("acct")
        else:
            raise AttemptedOverrideOfImmutableIdException

class UserManager(BaseUserManager):

    def create_user(self, username, password=None, account=None):
        acct = Account.objects.get(account_id=account)
        if not acct:
            raise AccountNotFound

        user = self.model()
        user.set_password(password)
        user.account = acct
        user.username = username
        user.generate_id()
        user.save()

        return user

    def create_superuser(self, username, password, account):
        if password is None:
            raise TypeError('Superusers must have a password.')

        user = self.create_user(username, password, account)
        user.is_superuser = True
        user.is_staff = True
        user.save()

        return user

class User(AbstractUser):
    user_id = models.CharField(max_length=20, unique=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, to_field="account_id")
    created = models.DateTimeField(auto_now_add=True, null=False)
    secret = models.TextField(null=True)
    tags = models.JSONField(default=dict)

    objects = UserManager()

    REQUIRED_FIELDS = [
        'account'
    ]

    def generate_id(self):
        if self.user_id is None:
            self.user_id = IdGenerator.generate("user")
        else:
            raise AttemptedOverrideOfImmutableIdException

    def __str__(self) -> str:
        return self.user_id


class UserAccessAccounts(AbstractBaseUser):
    access_id = models.CharField(max_length=20, unique=True)
    parent_user = models.ForeignKey(User, on_delete=models.CASCADE, to_field="user_id")
    created = models.DateTimeField(auto_now_add=True, null=False)
    secret = models.TextField(null=True)
    tags = models.JSONField(default=dict)

    USERNAME_FIELD = 'access_id'

    REQUIRED_FIELDS = [
        'parent_user'
    ]

    def generate_id(self):
        if self.access_id is not None:
            self.access_id = IdGenerator.generate("auth")
        else:
            raise AttemptedOverrideOfImmutableIdException
    
    def generate_secret(self, length=40):
        alphabet = string.ascii_letters + string.digits
        pw = ''.join(secrets.choice(alphabet) for i in range(length))
        self.set_password(pw)
        return pw

    def __str__(self) -> str:
        return self.access_id


class ServerServiceAccounts(models.Model):
    sa_id = models.CharField(max_length=20, unique=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, to_field="account_id")
    owner = models.CharField(max_length=40)
    created = models.DateTimeField(auto_now_add=True, null=False)
    active = models.BooleanField(default=True)
    secret = models.TextField()
    tags = models.JSONField(default=dict)

    def generate_id(self):
        if self.account_id is None:
            self.account_id = IdGenerator.generate("auth")
        else:
            raise AttemptedOverrideOfImmutableIdException

    def __str__(self) -> str:
        return self.sa_id
