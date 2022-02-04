import logging
import json
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status
from api.api_view import HelperView
from identity.models import User
from vmmanager.instance_definitions import InstanceDefinition
from vmmanager.models import VirtualMachine
from .exceptions import ClusterConfigurationError, ClusterAlreadyExists, ClusterDoesNotExist
from .models import KubeCluster
from .manager import KubeClusterManager
from .tasks import task_create_cluster
from .serializers import KubeClusterSerializer

logger = logging.getLogger(__name__)

class CreateKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        required_params = [
            "Name",
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
                name = request.POST["Name"],
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
        except ClusterAlreadyExists as e:
            return self.error_response(
                "Cluster with that name already exists.",
                status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()
        return self.success_response({"kube_cluster_id": cluster_id})
        


class DescribeKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, cluster_name:str):
        i = []

        try:
            if cluster_name == "all":
                vms = KubeCluster.objects.filter(
                    account=request.user.account
                )
            else:
                vms = []
                vms.append(KubeCluster.objects.get(
                    account=request.user.account,
                    name=cluster_name
                ))
            
            for cluster in vms:
                assoc_instances = []
                s_obj = KubeClusterSerializer(cluster).data
                for a_inst in s_obj['associated_instances']:
                    vm = VirtualMachine.objects.get(id=a_inst)
                    assoc_instances.append({
                        'instance_id': vm.instance_id,
                        'name': vm.tags['Name'] if "Name" in vm.tags else ""
                    })
                s_obj['associated_instances'] = assoc_instances
                i.append(s_obj)
        except KubeCluster.DoesNotExist as e:
            logger.debug(e)
            return self.not_found_response()
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()
        return self.success_response(i)
    

class ConfigKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, cluster_name:str):
        try:
            cluster_manager = KubeClusterManager(cluster_name)
        except ClusterDoesNotExist:
            return self.not_found_response()
        
        if cluster_manager.cluster_db.account != request.user.account:
            return self.not_found_response()
        
        try:
            config = cluster_manager.get_cluster_config(request.user)
            return self.success_response({"admin.conf": config})
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()
    


class TerminateKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, cluster_name:str):

        try:
            cluster_manager = KubeClusterManager(cluster_name)
        except ClusterDoesNotExist:
            return self.not_found_response()
        
        if cluster_manager.cluster_db.account != request.user.account:
            return self.not_found_response()
        
        try:
            cluster_manager.delete_cluster(request.user)
        except Exception as e:
            logger.exception(e)
            return self.internal_server_error_response()
        
        return self.success_response()
    

class ModifyKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, cluster_name):
        if missing_params := self.require_parameters(request, ["Action"]):
            return self.missing_parameter_response(missing_params)

        try:
            cluster_manager = KubeClusterManager(cluster_name)
        except ClusterDoesNotExist:
            return self.not_found_response()
        
        if cluster_manager.cluster_db.account != request.user.account:
            return self.not_found_response()

        action = request.POST['Action'].lower()
        logger.debug(f"Action: {action}")

        if action == 'add-node':
            required_params = [
                "InstanceType",
                "ImageId",
                "NetworkProfile",
                "NodeIp",
            ]
            optional_params = {
                "KeyName": None,
                "DiskSize": "30G",
                "Tags": {}
            }
            if missing_params := self.require_parameters(request, required_params):
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
            
            try:
                cluster_manager.add_node_to_cluster(
                    request.user,
                    instanceDefinition,
                    node_ip = request.POST['NodeIp'],
                    image_id = request.POST['ImageId'],
                    network_profile = request.POST['NetworkProfile'],
                    disk_size = request.POST["DiskSize"] if "DiskSize" in request.POST else optional_params["DiskSize"],
                    key_name = request.POST["KeyName"] if "KeyName" in request.POST else optional_params["KeyName"],
                    tags = tags
                )
            except ClusterConfigurationError as e:
                return self.error_response(
                    message = str(e),
                    status = status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.exception(e)
                return self.internal_server_error_response()

            return self.request_success_response()
        else:
            return self.error_response(
                "Unknown action",
                status = status.HTTP_400_BAD_REQUEST
            )


class InitAdminKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, cluster_id:str):
        # This endpoint is for service accounts
        if request.user.type != User.Type.SERVICE:
            return self.error_response(
                "Forbidden",
                status.HTTP_403_FORBIDDEN
            )
        
        # Also don't allow this request to modify anything
        # other than the account's cluster
        try:
            cluster_manager = KubeClusterManager(cluster_id = cluster_id)
        except ClusterDoesNotExist:
            return self.error_response(
                "Cluster is not configured",
                status.HTTP_400_BAD_REQUEST
            )
        
        if cluster_manager.cluster_db.account != request.user.account:
            return self.error_response(
                "Cluster is not configured",
                status.HTTP_400_BAD_REQUEST
            )
        
        json_data = json.loads(request.body)
        try:
            data = json_data['data']
        except KeyError:
            return self.error_response(
                "Malformed Data",
                status.HTTP_400_BAD_REQUEST
            )
        
        if data["Success"] == "true":
            # Store cluster secrets
            cluster_manager.set_cluster_secrets(request.user, data)
            cluster_manager.set_cluster_as_ready()
        else:
            cluster_manager.set_cluster_as_failed()

        return self.success_response()


class NodeAddAdminKubeCluster(HelperView, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, cluster_id:str):
        # This endpoint is for service accounts
        if request.user.type != User.Type.SERVICE:
            return self.error_response(
                "Forbidden",
                status.HTTP_403_FORBIDDEN
            )
        
        # Also don't allow this request to modify anything
        # other than the account's cluster
        try:
            cluster_manager = KubeClusterManager(cluster_id = cluster_id)
        except ClusterDoesNotExist:
            return self.error_response(
                "Cluster is not configured",
                status.HTTP_400_BAD_REQUEST
            )
        
        if cluster_manager.cluster_db.account != request.user.account:
            return self.error_response(
                "Cluster is not configured",
                status.HTTP_400_BAD_REQUEST
            )
        
        if 'Self' not in request.POST:
            return self.error_response(
                "Cluster is not configured",
                status.HTTP_400_BAD_REQUEST
            )
        
        try:
            vm = VirtualMachine.objects.get(instance_id=request.POST['Self'])
        except VirtualMachine.DoesNotExist:
            return self.error_response(
                "Unrecognized instance to add to cluster",
                status.HTTP_400_BAD_REQUEST
            )
        
        logger.debug(request.POST)
        if request.POST['Success'] == "true":
            # Associate this instance with the cluster
            cluster_manager.cluster_db.associated_instances.add(vm)
            cluster_manager.cluster_db.save()
        else:
            pass

        return self.success_response()
