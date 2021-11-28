import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from api.api_view import HelperView
from .manager import KubeClusterManager
from .tasks import task_create_cluster
from .serializers import KubeClusterSerializer

logger = logging.getLogger(__name__)

class CreateKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        required_params = [
            "KeyName",
        ]
        optional_params = []
        if missing_params := self.require_parameters(request, required_params):
            return self.missing_parameter_response(missing_params)
        
        manager = KubeClusterManager()
        cluster_id = manager.prepare_cluster()

        task_create_cluster(cluster_id, request.user)
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
