from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from echome.id_gen import IdGenerator
import string
import secrets

class AttemptedOverrideOfImmutableIdException(Exception):
    pass

class UserTypeNotSetException(Exception):
    pass

class AccountNotFound(Exception):
    pass

class Account(models.Model):
    # Unique identifier for this account.
    # Designated by the "acct-" prefix.
    account_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=40)
    created = models.DateTimeField(auto_now_add=True, null=False)
    secret = models.TextField(null=True)
    tags = models.JSONField(default=dict)

    def __str__(self) -> str:
        return self.account_id
    
    def generate_id(self):
        if self.account_id is None or self.account_id == "":
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

    class Type(models.TextChoices):
        REGULAR = 'RG', 'Regular'
        ACCESS_KEY = 'AK', 'Access Key'
        SERVICE = 'SR', 'Service'

    # Unique identifier for this login.
    # A primary or "main" user is designated by is_main = True and the "user-" prefix 
    # while an access account is designated by is_main = False and with "auth-" prefix.
    user_id = models.CharField(max_length=20, unique=True, db_index=True)

    type = models.CharField(
        max_length=2,
        choices=Type.choices,
        default=Type.REGULAR,
    )

    # Account this user belongs to
    account = models.ForeignKey(Account, on_delete=models.CASCADE, to_field="account_id")

    created = models.DateTimeField(auto_now_add=True, null=False)

    # Possibly not needed
    secret = models.TextField(null=True)

    # Tags for this user.
    tags = models.JSONField(default=dict)

    # Parent user must be specified if type == ACCESS_KEY or SERVICE
    parent = models.ForeignKey("self", on_delete=models.CASCADE, to_field="user_id", null=True)

    objects = UserManager()

    REQUIRED_FIELDS = [
        'account',
    ]

    # TODO: Investigate adding constraints 
    # class Meta:
    #     constraints = [
    #         models.UniqueConstraint(fields=['is_main'], condition=Q(status=False), name='')
    #     ]

    def generate_id(self):
        if self.user_id is None or self.user_id == "":
            if self.type == self.Type.REGULAR:
                t = "user"
            elif self.type == self.Type.ACCESS_KEY:
                t = "auth"
            elif self.type == self.Type.SERVICE:
                t = "svc"
            else:
                raise UserTypeNotSetException
            self.user_id = IdGenerator.generate(t)
        else:
            raise AttemptedOverrideOfImmutableIdException
        
        return self.user_id
    
    def generate_secret(self, length=40):
        alphabet = string.ascii_letters + string.digits
        pw = ''.join(secrets.choice(alphabet) for i in range(length))
        self.set_password(pw)
        return pw

    def __str__(self) -> str:
        return self.user_id
