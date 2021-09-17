import logging
from django.shortcuts import render
from django.http.response import JsonResponse
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from api.api_view import View
from .instance_definitions import InstanceDefinition, InvalidInstanceType
from .models import UserKey
from .vm_manager import VmManager, InvalidLaunchConfiguration, LaunchError

logger = logging.getLogger(__name__)

####################
# Namespace: vm 
# vm/
# /vm/create
# Example command:
# curl <URL>/v1/vm/create\?ImageId=gmi-fc1c9a62 \
# \&InstanceSize=standard.small \
# \&NetworkInterfacePrivateIp=172.16.9.10\/24 \
# \&NetworkInterfaceGatewayIp=172.16.9.1 \
# \&KeyName=echome
class CreateVM(View):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return JsonResponse({"got": True})

    def post(self, request):
        req_params = [
            "ImageId", 
            "InstanceType", 
            "NetworkProfile",
        ]
        if self.require_parameters(request, req_params):
            return self.missing_parameter_response()

        instance_class_size = request.POST["InstanceType"].split(".")
        try:
            instanceDefinition = InstanceDefinition(instance_class_size[0], instance_class_size[1])
        except InvalidInstanceType:
            return {"error": "Provided InstanceSize is not a valid type or size."}, 400
        
        tags = self.unpack_tags(request.args)

        disk_size = request.args["DiskSize"] if "DiskSize" in request.args else "10G"
        
        vm = VmManager()

        try:
            vm_id = vm.create_vm(
                user=request.user, 
                instanceType=instanceDefinition, 
                Tags=tags,
                KeyName=request.POST["KeyName"] if "KeyName" in request.POST else None,
                NetworkProfile=request.args["NetworkProfile"],
                PrivateIp=request.args["PrivateIp"] if "PrivateIp" in request.args else "",
                ImageId=request.args["ImageId"],
                DiskSize=disk_size    
            )
        except InvalidLaunchConfiguration as e:
            logger.debug(e)
            return {"error": "InvalidLaunchConfiguration: A supplied value was invalid and could not successfully build the virtual machine."}, 400
        except ValueError as e:
            logger.debug(e)
            return {"error": "ValueError: A supplied value was invalid and could not successfully build the virtual machine."}, 400
        except LaunchError as e:
            logger.error(e)
            return {"error": "There was an error when creating the instance."}, 500
        except Exception as e:
            logger.error(e)
            return {"error": "There was an error when processing the request."}, 500
                
        return JsonResponse({"vm_id": vm_id})