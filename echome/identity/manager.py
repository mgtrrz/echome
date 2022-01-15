import logging
import datetime
from rest_framework_simplejwt.tokens import RefreshToken, Token
from .models import User, Account

logger = logging.getLogger(__name__)

class ServiceAccount:

    def create(self):
        pass

    def generate_jwt_token(self, service_acount:User):
        if service_acount.type != User.Type.SERVICE:
            raise Exception #TODO: Clarify
        
        refresh:Token = RefreshToken.for_user(service_acount)
        # Setting the timedelta manually currently does not work
        refresh.access_token.set_exp(lifetime=datetime.timedelta(minutes=15))
        return str(refresh.access_token)
