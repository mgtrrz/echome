import logging
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import viewsets, status
from api.api_view import HelperView
from .models import UserKey
from .manager import UserKeyManager
from .serializers import UserKeySerializer
from .exceptions import *

logger = logging.getLogger(__name__)

class CreateKeys(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        params = self.require_parameters(request, [
            "Action",
            "KeyName",
        ])
        if params:
            return self.missing_parameter_response(params)
        
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
            pass

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

    def get(self, request):
        return Response({"got": True})

    def post(self, request, vm_id:str):
        try:
            VmManager().terminate_instance(vm_id, request.user)
        except VirtualMachineDoesNotExist:
            return self.not_found_response()
        except Exception:
            return self.internal_server_error_response()
        
        return self.success_response()


class ModifyKeys(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"got": True})

    def post(self, request, vm_id:str):
        req_params = [
            "Action",
        ]
        if self.require_parameters(request, req_params):
            return self.missing_parameter_response()

        action = request.POST['Action']
        logger.debug("Action:")
        logger.debug(action)
        if action == 'stop':
            try:
                VmManager().stop_instance(vm_id)
            except VirtualMachineDoesNotExist:
                return self.not_found_response()
            except Exception:
                return self.internal_server_error_response()
        
            return self.success_response()
        elif action == 'start':
            try:
                VmManager().start_instance(vm_id)
            except VirtualMachineDoesNotExist:
                return self.not_found_response()
            except VirtualMachineConfigurationException:
                return self.error_response(
                    "Could not start VM due to configuration issue. See logs for more details.",
                    status = status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            except Exception:
                return self.internal_server_error_response()
        else:
            return self.error_response(
                    "Unknown action",
                    status = status.HTTP_400_BAD_REQUEST
                )
        return self.success_response()
        