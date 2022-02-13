import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from api.api_view import HelperView
from .models import VirtualNetwork
from .manager import VirtualNetworkManager
from .exceptions import InvalidNetworkConfiguration, InvalidNetworkName
from .serializers import NetworkSerializer

logger = logging.getLogger(__name__)

class CreateNetwork(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        required_params = [
            "Type",
            "Name",
            "Network", 
            "Prefix", 
            "Gateway", 
            "DnsServers", 
            "Bridge",
        ]
        if missing_params := self.require_parameters(request, required_params):
            return self.missing_parameter_response(missing_params)
        
        if request.POST["Type"] == "BridgeToLan":
            type = VirtualNetwork.Type.BRIDGE_TO_LAN
        else:
            type = VirtualNetwork.Type.NAT
            return self.bad_request("Other network types not currently supported")

        tags = self.unpack_tags(request)
        vnet_manager = VirtualNetworkManager()

        try:
            new_network_id = vnet_manager.create_bridge_to_lan_network(
                name=request.POST["Name"],
                user=request.user,
                type=type,
                network=request.POST["Network"],
                prefix=request.POST["Prefix"],
                gateway=request.POST["Gateway"],
                dns_servers=self.unpack_comma_separated_list("DnsServers", request.POST),
                bridge=request.POST["Bridge"],
                tags=tags,
            )
        except InvalidNetworkName as e:
            return self.bad_request(str(e))
        except InvalidNetworkConfiguration as e:
            return self.bad_request(str(e))
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()
    
        return self.success_response({'virtual_network': new_network_id})


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
                vnets.append(VirtualNetwork.objects.get(
                    network_id=net_id,
                    account=request.user.account,
                ))
            
            for vnet in vnets:
                networks.append(NetworkSerializer(vnet).data)

        except VirtualNetwork.DoesNotExist as e:
            logger.debug(e)
            return self.not_found_response()
        except Exception as e:
            logger.exception(e)
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
        