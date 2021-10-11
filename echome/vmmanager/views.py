import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status
from api.api_view import HelperView
from .instance_definitions import InstanceDefinition, InvalidInstanceType
from .models import VirtualMachine
from .serializers import VirtualMachineSerializer
from .manager import VmManager
from .tasks import task_create_image, task_stop_instance, task_terminate_instance
from .vm_instance import VirtualMachineInstance
from .exceptions import InvalidLaunchConfiguration, LaunchError, VirtualMachineDoesNotExist, VirtualMachineConfigurationError

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
class CreateVM(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_params = [
            "ImageId", 
            "InstanceType", 
            "NetworkProfile",
        ]
        if missing_params := self.require_parameters(request, req_params):
            return self.missing_parameter_response(missing_params)

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
                instance_def=instanceDefinition, 
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


class DescribeVM(HelperView, APIView):
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
                state, state_int, _  = VirtualMachineInstance(vm_id).get_vm_state(vm.instance_id)
                j_obj["state"] = {
                    "code": state_int,
                    "state": state,
                }
                i.append(j_obj)
        except VirtualMachine.DoesNotExist as e:
            logger.debug(e)
            return self.not_found_response()
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()

        return self.success_response(i)


class TerminateVM(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, vm_id:str):
        try:
            task_terminate_instance.delay(vm_id, request.user.user_id)
        except VirtualMachineDoesNotExist:
            return self.not_found_response()
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()
        
        return self.request_success_response()


class ModifyVM(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, vm_id:str):
        if missing_params := self.require_parameters(request, ["Action"]):
            return self.missing_parameter_response(missing_params)

        action = request.POST['Action'].lower()
        logger.debug(f"Action: {action}")

        if action == 'stop':
            try:
                instance = VirtualMachineInstance(vm_id)
                instance.stop(wait=False)
            except VirtualMachineDoesNotExist:
                return self.not_found_response()
            except Exception:
                return self.internal_server_error_response()
        
            return self.success_response()
        elif action == 'start':
            try:
                instance = VirtualMachineInstance(vm_id)
                instance.start()
            except VirtualMachineDoesNotExist:
                return self.not_found_response()
            except VirtualMachineConfigurationError:
                return self.error_response(
                    "Could not start VM due to configuration issue. See logs for more details.",
                    status = status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            except Exception as e:
                logger.exception(e)
                return self.internal_server_error_response()
        elif action == 'create-image':
            req_params = ["Name", "Description"]
            if missing_params := self.require_parameters(request, req_params):
                return self.missing_parameter_response(missing_params)
            try:
                result = VmManager().create_virtual_machine_image(
                    vm_id, 
                    request.user,
                    request.POST["Name"],
                    request.POST["Description"],
                    self.unpack_tags(request)
                )
            except Exception as e:
                logger.exception(e)
                return self.internal_server_error_response()
            return self.success_response(result)
        else:
            return self.error_response(
                    "Unknown action",
                    status = status.HTTP_400_BAD_REQUEST
                )
        return self.success_response()
    
        