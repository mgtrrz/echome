import logging
from django.shortcuts import render
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets, status
from api.api_view import View
from identity.models import User
from .instance_definitions import InstanceDefinition, InvalidInstanceType
from .models import UserKey, VirtualMachine
from .serializers import VirtualMachineSerializer
from .vm_manager import *

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
        return Response({"got": True})

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
            logger.error(e)
            return self.error_response(
                "There was an error when creating the instance.",
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(e)
            return self.error_response(
                "There was an error when processing the request.",
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )
                
        return Response({"vm_id": vm_id})

class DescribeVM(View):
    permission_classes = [IsAuthenticated]

    def get(self, request, vm_id:str):
        i = []

        try:
            if vm_id == "all":
                vms = VirtualMachine.objects.filter(
                    account=request.user.account
                )
            else:
                vms = []
                vms.append(VirtualMachine.objects.get(
                    account=request.user.account,
                    instance_id=vm_id
                ))
            
            for vm in vms:
                j_obj = VirtualMachineSerializer(vm).data
                state, state_int, _  = VmManager().get_vm_state(vm.instance_id)
                j_obj["state"] = {
                    "code": state_int,
                    "state": state,
                }
                i.append(j_obj)
        except VirtualMachine.DoesNotExist as e:
            logger.debug(e)
            return self.error_response(
                "Virtual Machine does not exist.",
                status = status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.debug(e)
            return self.error_response(
                "Internal Server Error.",
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(i)
