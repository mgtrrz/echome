import string
import logging
import secrets
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from echome.id_gen import IdGenerator
from echome.exceptions import AttemptedOverrideOfImmutableIdException
from .exceptions import AccountNotFoundError, UserTypeNotSetException

logger = logging.getLogger(__name__)

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
            raise AccountNotFoundError

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
    
    
    def create_service_account(self, account):
        svc = self.model()
        svc.account = account
        svc.type = User.Type.SERVICE
        svc.generate_id()
        svc.username = svc.user_id
        svc.save()

        return svc


class User(AbstractUser):

    # Unique identifier for this login.
    # A primary or "main" user is designated by the "user-" prefix and type REGULAR
    # while an access account is designated with "auth-" prefix and the type ACCESS_KEY.
    user_id = models.CharField(max_length=20, unique=True, db_index=True)

    # User type: Identifies the type of user. A single user that interacts with ecHome
    #   must have a REGULAR user at a minimum and can have multiple ACCESS_KEY 'users' associated
    #   with the REGULAR user.
    # REGULAR: A regular user identifies a person who can log in to the UI and has permissions 
    #   set to make changes on the cluster. This type of user can also have Django's
    #   superuser flag set which will allow them to make changes to the cluster.
    #   Regular users/credentials cannot be used to obtain a token for the API; an Access
    #   Key must be created instead.
    # ACCESS_KEY: A user that is used for API access. This is not a unique user and instead
    #   has a parent user which must be tied to a REGULAR user. 
    # SERVICE: A user that is created by ecHome for making changes on behalf of the
    #   account. Users do not see this type.
    class Type(models.TextChoices):
        REGULAR = 'RG', 'Regular'
        ACCESS_KEY = 'AK', 'Access Key'
        SERVICE = 'SR', 'Service'

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
    

    def get_top_level_user(self):
        if self.type == User.Type.ACCESS_KEY:
            return self.parent
        else:
            return self


    def __str__(self) -> str:
        return self.user_id
