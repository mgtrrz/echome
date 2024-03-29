import logging
import datetime
from rest_framework_simplejwt.tokens import RefreshToken, Token
from .models import User, Account

logger = logging.getLogger(__name__)

class ServiceAccount:

    def create_or_get(self, account:Account):
        objs = User.objects.filter(account=account,type=User.Type.SERVICE)
        if objs:
            return objs[0]
        # TODO: Namespace service accounts
        return User.objects.create_service_account(account=account)


    def generate_jwt_token(self, service_acount:User, expiration=None):
        if service_acount.type != User.Type.SERVICE:
            raise Exception #TODO: Clarify
        
        refresh:Token = RefreshToken.for_user(service_acount)
        # Setting the timedelta manually currently does not work
        refresh.access_token.set_exp(lifetime=datetime.timedelta(minutes=15))
        return str(refresh.access_token)
