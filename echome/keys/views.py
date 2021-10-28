import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status
from api.api_view import HelperView
from .models import UserKey
from .manager import UserKeyManager
from .serializers import UserKeySerializer
from .exceptions import KeyDoesNotExist, KeyNameAlreadyExists, PublicKeyAlreadyExists

logger = logging.getLogger(__name__)

class CreateKeys(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        required_params = [
            "Action",
            "KeyName",
        ]
        if missing_params := self.require_parameters(request, required_params):
            return self.missing_parameter_response(missing_params)
        
        if request.POST["Action"] == "new":
            try:
                new_key, private_key = UserKeyManager().generate_sshkey(request.user, request.POST["KeyName"])
            except KeyNameAlreadyExists:
                return self.error_response(
                    "Key (KeyName) with that name already exists.",
                    status = status.HTTP_400_BAD_REQUEST
                )
            
            obj = UserKeySerializer(new_key).data
            obj["private_key"] = private_key
            return self.success_response(obj)
     
        elif request.POST["Action"] == "import":
            try:
                new_key = UserKeyManager().store_key(request.user, request.POST["KeyName"], request.POST["PublicKey"])
            except KeyNameAlreadyExists:
                return self.error_response(
                    "Key (KeyName) with that name already exists.",
                    status = status.HTTP_400_BAD_REQUEST
                )
            except PublicKeyAlreadyExists:
                return self.error_response(
                    "Key (PublicKey) with that value already exists.",
                    status = status.HTTP_400_BAD_REQUEST
                )
            
            obj = UserKeySerializer(new_key).data
            return self.success_response(obj)


class DescribeKeys(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, key_name:str):
        i = []

        try:
            if key_name == "all":
                keys = UserKey.objects.filter(
                    account=request.user.account
                )
            else:
                keys = []
                keys.append(UserKey.objects.get(
                    account=request.user.account,
                    name=key_name
                ))
            
            for key in keys:
                k_obj = UserKeySerializer(key).data
                i.append(k_obj)

        except UserKey.DoesNotExist as e:
            logger.debug(e)
            return self.not_found_response()
        except Exception as e:
            logger.debug(e)
            return self.internal_server_error_response()

        return self.success_response(i)


class DeleteKeys(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, key_name:str):
        try:
            key:UserKey = UserKey.objects.get(
                account=request.user.account,
                name=key_name
            )

            key.delete()
        except UserKey.DoesNotExist:
            return self.not_found_response()
        except Exception:
            return self.internal_server_error_response()
        
        return self.success_response()


class ModifyKeys(HelperView, APIView):
    permission_classes = [IsAuthenticated]
