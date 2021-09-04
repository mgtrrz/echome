from django.shortcuts import render
from django.http.response import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from api.api_view import View
from .instance_definitions import Instance, InvalidInstanceType

####################
# Namespace: vm 
# vm/
1
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
            "InstanceSize", 
            "NetworkProfile",
        ]
        if self.require_parameters(request, req_params):
            return self.missing_parameter_response()

        iTypeSize = request.POST["InstanceSize"].split(".")
        try:
            instanceDefinition = Instance(iTypeSize[0], iTypeSize[1])
        except InvalidInstanceType:
            return {"error": "Provided InstanceSize is not a valid type or size."}, 400
        
        tags = self.unpack_tags(request.args)

        disk_size = request.args["DiskSize"] if "DiskSize" in request.args else "10G"
        
        key_name = None
        if "KeyName" in request.POST:
            try:
                KeyStore().get(user, request.args["KeyName"])
                key_name = request.args["KeyName"]
            except KeyDoesNotExist:
                return {"error": "Provided KeyName does not exist."}, 400

        try:
            vm_id = vm.create_vm(
                user=user, 
                instanceType=instanceDefinition, 
                Tags=tags,
                KeyName=key_name,
                NetworkProfile=request.args["NetworkProfile"],
                PrivateIp=request.args["PrivateIp"] if "PrivateIp" in request.args else "",
                ImageId=request.args["ImageId"],
                DiskSize=disk_size    
            )
        except InvalidLaunchConfiguration as e:
            logging.debug(e)
            return {"error": "A supplied value was invalid and could not successfully build the virtual machine."}, 400
        except LaunchError as e:
            logging.error(e)
            return {"error": "There was an error when creating the instance."}, 500
        except Exception as e:
            logging.error(e)
            return {"error": "There was an error when processing the request."}, 500
                
        return JsonResponse({"vm_id": vm_id})