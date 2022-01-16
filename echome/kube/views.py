import logging
import json
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status
from api.api_view import HelperView
from identity.models import User
from .exceptions import ClusterConfigurationError
from .manager import KubeClusterManager
from .tasks import task_create_cluster
from .serializers import KubeClusterSerializer

logger = logging.getLogger(__name__)

class CreateKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        required_params = [
            "KeyName",
            "InstanceType",
            "ImageId",
            "NetworkProfile",
            "ControllerIp",
        ]
        optional_params = {
            "KubeVersion": "1.23.0",
            "KeyName": None,
            "DiskSize": "30G",
            "Tags": {}
        }
        if missing_params := self.require_parameters(request, required_params):
            return self.missing_parameter_response(missing_params)
        
        tags = self.unpack_tags(request)

        manager = KubeClusterManager()

        try:
            # I don't like doing this
            # Need to figure out a way to clean this up
            
            cluster_id = manager.prepare_cluster(
                user = request.user,
                instance_def = request.POST["InstanceType"],
                image_id = request.POST["ImageId"],
                network_profile = request.POST["NetworkProfile"],
                controller_ip = request.POST["ControllerIp"],
                kubernetes_version = request.POST["KubeVersion"] if "KubeVersion" in request.POST else optional_params["KubeVersion"],
                key_name = request.POST["KeyName"] if "KeyName" in request.POST else optional_params["KeyName"],
                tags = tags,
            )

            task_create_cluster.delay(
                prepared_cluster_id = cluster_id,
                user_id = request.user.user_id,
                instance_def = request.POST["InstanceType"],
                image_id = request.POST["ImageId"],
                network_profile = request.POST["NetworkProfile"],
                controller_ip = request.POST["ControllerIp"],
                kubernetes_version = request.POST["KubeVersion"] if "KubeVersion" in request.POST else optional_params["KubeVersion"],
                key_name = request.POST["KeyName"] if "KeyName" in request.POST else optional_params["KeyName"],
                disk_size = request.POST["DiskSize"] if "DiskSize" in request.POST else optional_params["DiskSize"]
            )
        except ClusterConfigurationError as e:
            logger.exception(e)
            return self.error_response(
                "There was an error when creating the cluster.",
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()
        return self.success_response({"kube_cluster_id": cluster_id})
        


class DescribeKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, key_name:str):
        pass
    


class TerminateKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, key_name:str):
        pass
    

class ModifyKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]


class InitAdminKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, cluster_id:str):
        print(request.user)
        if request.user.type != User.Type.SERVICE:
            return self.error_response(
                "Forbidden",
                status.HTTP_403_FORBIDDEN
            )
        
        json_data = json.loads(request.body)
        try:
            data = json_data['data']
        except KeyError:
            return self.error_response(
                "Malformed Data",
                status.HTTP_400_BAD_REQUEST
            )

        print(cluster_id)
        print(request)
        print(request.POST)
        print("Json data:")
        print(data)
        return self.success_response()
