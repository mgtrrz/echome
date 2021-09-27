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

    def get(self, request):
        return Response({"got": True})

    def post(self, request):
        req_params = [
            "ImageId", 
            "InstanceType", 
            "NetworkProfile",
        ]
        logger.debug(request)
        if self.require_parameters(request, req_params):
            return self.missing_parameter_response()

        try:
            instance_class_size = request.POST["InstanceType"].split(".")
            instanceDefinition = InstanceDefinition(instance_class_size[0], instance_class_size[1])
        except Exception as e:
            logger.debug(e)
            return self.error_response(
                "Provided InstanceSize is not a valid type or size.",
                status.HTTP_400_BAD_REQUEST
            )
        
        tags = self.unpack_tags(request)

        disk_size = request.POST["DiskSize"] if "DiskSize" in request.POST else "10G"
        
        vm = VmManager()

        try:
            vm_id = vm.create_vm(
                user=request.user, 
                instanceType=instanceDefinition, 
                Tags=tags,
                KeyName=request.POST["KeyName"] if "KeyName" in request.POST else None,
                NetworkProfile=request.POST["NetworkProfile"],
                PrivateIp=request.POST["PrivateIp"] if "PrivateIp" in request.POST else "",
                ImageId=request.POST["ImageId"],
                DiskSize=disk_size,
                EnableVnc=True if "EnableVnc" in request.POST and request.POST["EnableVnc"] == "true" else False,
                VncPort=request.POST["VncPort"] if "VncPort" in request.POST else None,
            )
        except InvalidLaunchConfiguration as e:
            logger.debug(e)
            return self.error_response(
                "InvalidLaunchConfiguration: A supplied value was invalid and could not successfully build the virtual machine.",
                status = status.HTTP_400_BAD_REQUEST
            )
        except ValueError as e:
            logger.debug(e)
            return self.error_response(
                "ValueError: A supplied value was invalid and could not successfully build the virtual machine.",
                status = status.HTTP_400_BAD_REQUEST
            )
        except LaunchError as e:
            logger.exception(e)
            return self.error_response(
                "There was an error when creating the instance.",
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()
                
        return self.success_response({"virtual_machine_id": vm_id})


class DescribeKeys(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, key_id:str):
        i = []

        try:
            if key_id == "all":
                keys = UserKey.objects.filter(
                    account=request.user.account
                )
            else:
                keys = []
                keys.append(UserKey.objects.get(
                    account=request.user.account,
                    instance_id=key_id
                ))
            
            for key in keys:
                k_obj = UserKeySerializer(key).data
                i.append(k_obj)

        except KeyDoesNotExist as e:
            logger.debug(e)
            return self.not_found_response()
        except Exception as e:
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
        