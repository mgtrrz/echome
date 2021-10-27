import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status
from api.api_view import HelperView
from .models import KubeCluster
from .manager import KubeClusterManager
from .serializers import KubeClusterSerializer

logger = logging.getLogger(__name__)

class CreateKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        required_params = [
            "Action",
            "KeyName",
        ]
        if missing_params := self.require_parameters(request, required_params):
            return self.missing_parameter_response(missing_params)
        


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
