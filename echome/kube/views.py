import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from api.api_view import HelperView
from .manager import KubeClusterManager
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
            "KubeVersion": "1.22",
            "KeyName": None,
            "DiskSize": "30G"
        }
        if missing_params := self.require_parameters(request, required_params):
            return self.missing_parameter_response(missing_params)
        
        manager = KubeClusterManager()

        try:
            cluster_id = manager.prepare_cluster(
                user_id = request.user.user_id,
                instance_def = request.POST["InstanceType"],
                image_id = request.POST["ImageId"],
                network_profile = request.POST["NetworkProfile"],
                controller_ip = request.POST["ControllerIp"],
                kubernetes_version = request.POST["KubeVersion"] if "KubeVersion" in request.POST else optional_params["KubeVersion"],
                key_name = request.POST["KeyName"] if "KeyName" in request.POST else optional_params["KeyName"],
                disk_size = request.POST["DiskSize"] if "DiskSize" in request.POST else optional_params["DiskSize"],
            )
        except Exception as e:
            pass
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
