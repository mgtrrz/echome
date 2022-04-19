import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status
from api.api_view import HelperView
from .instance_definitions import InstanceDefinition, InvalidInstanceType
from .models import VirtualMachine, Volume, Image
from .serializers import VirtualMachineSerializer, VolumeSerializer, ImageSerializer
from .image_manager import ImageManager
from .vm_manager import VmManager
from .tasks import task_create_image, task_terminate_instance
from .vm_instance import VirtualMachineInstance
from .exceptions import (
    InvalidLaunchConfiguration, 
    LaunchError,
    VirtualMachineDoesNotExist,
    VirtualMachineConfigurationError, 
    InvalidImagePath, 
    ImageAlreadyExistsError
)

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
        optional_params = {
            "KeyName": None,
            "DiskSize": "10G",
            "PrivateIp": "",
            "EnableVnc": "false",
            "VncPort": "false",
            "UserDataScript": None,
            "Tags": {}
        }
        if missing_params := self.require_parameters(request, req_params):
            return self.missing_parameter_response(missing_params)

        try:
            instance_class_size = request.POST["InstanceType"].split(".")
            instanceDefinition = InstanceDefinition(instance_class_size[0], instance_class_size[1])
        except Exception as e:
            logger.debug(e)
            return self.bad_request("Provided InstanceSize is not a valid type or size.")
        
        tags = self.unpack_tags(request)
        
        vm = VmManager()
        try:
            vm_id = vm.create_vm(
                user = request.user, 
                instance_def = instanceDefinition, 
                Tags = tags,
                KeyName = request.POST.get("KeyName", optional_params["KeyName"]),
                NetworkProfile = request.POST["NetworkProfile"],
                PrivateIp = request.POST.get("PrivateIp", optional_params["PrivateIp"]),
                ImageId = request.POST["ImageId"],
                DiskSize = request.POST.get("DiskSize", optional_params["DiskSize"]),
                EnableVnc = True if "EnableVnc" in request.POST and request.POST["EnableVnc"] == "true" else False,
                VncPort = request.POST.get("VncPort", optional_params['VncPort']),
                UserDataScript = request.POST.get("UserDataScript", optional_params['UserDataScript']),
                EfiBoot = "false", #TODO: Configurable Option
            )
        except InvalidLaunchConfiguration as e:
            logger.debug(e)
            return self.bad_request("InvalidLaunchConfiguration: A supplied value was invalid and could not successfully build the virtual machine.")
        except ValueError as e:
            logger.debug(e)
            return self.bad_request("ValueError: A supplied value was invalid and could not successfully build the virtual machine.")
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
                state, state_int, _  = VirtualMachineInstance(vm.instance_id).get_vm_state()
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
            VirtualMachineInstance(vm_id)
        except VirtualMachineDoesNotExist:
            return self.not_found_response()

        try:
            task_terminate_instance.delay(vm_id, request.user.user_id)
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()
        
        return self.request_success_response()


class ModifyVM(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, vm_id:str):
        if missing_params := self.require_parameters(request, ["Action"]):
            return self.missing_parameter_response(missing_params)

        try:
            instance = VirtualMachineInstance(vm_id)
        except VirtualMachineDoesNotExist:
            return self.not_found_response()

        action = request.POST['Action'].lower()
        logger.debug(f"Action: {action}")

        if action == 'stop':
            try:
                instance.stop(wait=False)
            except Exception:
                return self.internal_server_error_response()
        
            return self.success_response()
        elif action == 'start':
            try:
                instance.start()
            except VirtualMachineConfigurationError:
                return self.error_response(
                    "Could not start VM due to configuration issue. See logs for more details.",
                    status = status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            except Exception as e:
                logger.exception(e)
                return self.internal_server_error_response()
        elif action == 'create-image':
            req_params = [
                "Name", 
                "Description"
            ]
            if missing_params := self.require_parameters(request, req_params):
                return self.missing_parameter_response(missing_params)
            
            image_manager = ImageManager()
            new_vmi_id = image_manager.prepare_user_image(
                request.user,
                request.POST["Name"],
                request.POST["Description"],
                self.unpack_tags(request),
            )
            logger.debug(f"New VMI ID: {new_vmi_id}")
            
            task_create_image.delay(
                vm_id, 
                request.user.user_id, 
                prepared_id = new_vmi_id
            )

            return self.request_success_response(new_vmi_id)
        else:
            return self.bad_request("Unknown action")
        return self.success_response()


class CreateVolume(HelperView, APIView):
    pass


class DeleteVolume(HelperView, APIView):
    pass  


class DescribeVolume(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vol_id:str):
        try:
            if vol_id == "all":
                vols = Volume.objects.filter(
                    account=request.user.account
                )
            else:
                vols = []
                vols.append(Volume.objects.get(
                    account=request.user.account,
                    volume_id=vol_id
                ))
            
            i = [VolumeSerializer(vol).data for vol in vols]
        except Volume.DoesNotExist as e:
            logger.debug(e)
            return self.not_found_response()
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()

        return self.success_response(i)


class ModifyVolume(HelperView, APIView):
    pass


class RegisterImage(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_params = [
            "ImagePath", 
            "ImageName", 
            "ImageDescription"
        ]
        if missing_params := self.require_parameters(request, req_params):
            return self.missing_parameter_response(missing_params)
        
        image_manager = ImageManager()
        try:
            id = image_manager.register_guest_image(
                request.POST["ImagePath"],
                request.POST["ImageName"],
                request.POST["ImageDescription"],
            )
        except InvalidImagePath:
            return self.error_response(
                "ValueError: Image does not exist at specified path.",
                status = status.HTTP_400_BAD_REQUEST
            )
        except ImageAlreadyExistsError:
            return self.error_response(
                "ValueError: Image already exists.",
                status = status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()
            
        return self.success_response(id)


class DeleteImage(HelperView, APIView):
    pass  


class DescribeImage(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, img_type:str, img_id:str):
        if img_type not in ["guest", "user"]:
            return self.error_response(
                "Unknown type",
                status = status.HTTP_404_NOT_FOUND
            )
        
        try:
            if img_type == "guest":
                if img_id == "all":
                    images = Image.objects.filter(
                        image_type=Image.ImageType.GUEST
                    )
                else:
                    images = []
                    images.append(Image.objects.get(
                        image_type=Image.ImageType.GUEST,
                        image_id=img_id
                    ))
            elif img_type == "user":
                if img_id == "all":
                    images = Image.objects.filter(
                        image_type=Image.ImageType.USER,
                        account=request.user.account,
                    )
                else:
                    images = []
                    images.append(Image.objects.get(
                        image_type=Image.ImageType.USER,
                        image_id=img_id,
                        account=request.user.account,
                    ))
            else:
                return self.bad_request("Image is type other than Guest or User")
            
            i = [ImageSerializer(image).data for image in images]
        except Image.DoesNotExist as e:
            logger.debug(e)
            return self.not_found_response()
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()

        return self.success_response(i)


class ModifyImage(HelperView, APIView):
    pass
