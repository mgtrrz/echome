import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import viewsets, status
from api.api_view import HelperView
from identity.models import User
from .models import VirtualNetwork
from .serializers import NetworkSerializer

logger = logging.getLogger(__name__)

class CreateNetwork(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pass

class DescribeNetwork(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, net_id:str):
        networks = []

        try:
            if net_id == "all":
                vnets = VirtualNetwork.objects.filter(
                    account=request.user.account,
                )
            else:
                vnets = []
                networks = VirtualNetwork.objects.filter(
                    network_id=net_id,
                    account=request.user.account,
                )
            
            for vnet in vnets:
                networks.append(NetworkSerializer(vnet).data)

        except VirtualNetwork.DoesNotExist as e:
            logger.debug(e)
            return self.not_found_response()
        except Exception as e:
            return self.internal_server_error_response()
        
        return self.success_response(networks)
        

class TerminateNetwork(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, net_id:str):
        pass

class ModifyNetwork(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, net_id:str):
        pass
        