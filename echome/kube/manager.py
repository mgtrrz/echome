import logging
import json
from string import Template
from django.apps import apps
from django.urls import reverse
from echome.config import ecHomeConfig
from identity.models import User
from identity.manager import ServiceAccount
from vault.vault import Vault
from vault.exceptions import SecretDoesNotExistError
from network.manager import VirtualNetworkManager
from keys.manager import UserKeyManager
from vmmanager.instance_definitions import InstanceDefinition
from vmmanager.vm_manager import VmManager
from vmmanager.tasks import task_terminate_instance
from vmmanager.cloudinit import CloudInitFile
from vmmanager.image_manager import ImageManager
from vmmanager.models import VirtualMachine
from .models import KubeCluster
from .exceptions import ClusterConfigurationError, ClusterGetConfigurationError

logger = logging.getLogger(__name__)

class KubeClusterManager:

    cluster_db: KubeCluster = None
    vault_mount_point = "kube"

    def __init__(self, cluster_id:str = None) -> None:
        if cluster_id:
            self.cluster_db = KubeCluster.objects.get(cluster_id=cluster_id)
        else:
            self.cluster_db = KubeCluster()


    def _prepare_cluster_db(self, user:User, tags:dict = None):
        self.cluster_db.generate_id()
        self.cluster_db.tags = tags if tags else {}
        self.cluster_db.account = user.account
        self.cluster_db.save()
        return self.cluster_db.cluster_id
    

    def delete_cluster_db(self):
        pass

    def set_cluster_as_failed(self):
        logger.debug("Setting cluster status as FAILED")
        self.cluster_db.status = KubeCluster.Status.FAILED
        self.cluster_db.save()
    
    def set_cluster_as_ready(self):
        logger.debug("Setting cluster status as READY")
        self.cluster_db.status = KubeCluster.Status.READY
        self.cluster_db.save()
    

    def get_cluster_config(self, user:User):
        vault = Vault()
        try:
            conf = vault.get_secret(
                self.vault_mount_point, 
                f"{user.account.account_id}/{self.cluster_db.cluster_id}/admin"
            )
            conf = conf["data"]["data"]["admin.conf"]
        except Exception:
            logger.debug(f"Could not extract config from Vault for {self.cluster_db.cluster_id}/admin")
            raise ClusterGetConfigurationError("Could not retrieve config for specified cluster.")
        
        return conf
    

    def set_cluster_secrets(self, user:User, details:dict):
        vault = Vault()

        secrets = {
            'ca_sha': details['CaSha'],
            'admin.conf': details['AdminConf'],
            'kubeadm_token': details['KubeadmToken']
        }

        vault.store_dict(
            self.vault_mount_point, 
            path_name=f"{user.account.account_id}/{self.cluster_db.cluster_id}",
            value=secrets
        )
    

    def delete_cluster(self, user:User):
        logger.debug(f"Received request to terminate cluster: {self.cluster_db.cluster_id}")
        self.cluster_db.status = KubeCluster.Status.DELETING
        self.cluster_db.save()

        # Delete Entry in Vault
        logger.debug("Deleting Vault entries for this cluster")
        vault = Vault()
        vault.delete_key(self.vault_mount_point, f"{self.cluster_db.account.account_id}/{self.cluster_db.cluster_id}")

        # Delete kube cluster by setting state to TERMINATED
        self.cluster_db.primary = None
        self.cluster_db.status = KubeCluster.Status.TERMINATED
        self.cluster_db.save()

        # Delete controller VM
        controller = self.cluster_db.primary
        logger.debug("Terminating controller instance")
        task_terminate_instance.delay(controller.instance_id, user.user_id)

        return True
    

    def prepare_cluster(self, user:User, instance_def: InstanceDefinition, \
        controller_ip:str, image_id:str, network_profile:str, kubernetes_version:str = "1.22", 
        key_name:str = None, tags:dict = None):
        """This function checks all the values to make sure they're
        valid, then creates a row in the database for this cluster in the BUILDING state.

        Args:
            user (User): [description]
            instance_def (InstanceDefinition): [description]
            image_id (str): [description]
            network_profile (str): [description]
            kubernetes_version (str, optional): [description]. Defaults to "1.22".
            key_name (str, optional): [description]. Defaults to None.
            disk_size (str, optional): [description]. Defaults to "50G".
            tags (dict, optional): [description]. Defaults to None.
        """

        # Checking inputs to make sure everything is correct
        try:
            instance_definition = InstanceDefinition(instance_def)
            network = VirtualNetworkManager(network_profile, user)
            network.validate_ip(controller_ip)
            if key_name:
                UserKeyManager(key_name, user)
            image = ImageManager(image_id)
        except Exception as e:
            logger.exception(e)
            raise ClusterConfigurationError

        cluster_id = self._prepare_cluster_db(user, tags=tags)
        return cluster_id


    def create_cluster(self, user:User, instance_def: InstanceDefinition, \
        controller_ip:str, image_id:str, network_profile:str, disk_size:str, kubernetes_version:str = "1.23", 
        key_name:str = None):

        if self.cluster_db is None:
            raise ClusterConfigurationError("cluster_db is not set!")

        files = []

        cluster_info_file_path = "/root/cluster_info.yaml"
        echome_info_file_path = "/root/server_info.yaml"
        kubeadm_template_path = "/root/kubeadm_template.yaml"
        sh_script_path = "/root/init_kube_debian.sh"
        

        # Create a service account and token for the controller to send
        # information back to us
        svc_acct = ServiceAccount()
        service_account = svc_acct.create_or_get(user.account)
        token = svc_acct.generate_jwt_token(service_account)

        files.append(CloudInitFile(
            path = echome_info_file_path,
            content = json.dumps({
                "server_addr": ecHomeConfig.EcHome().api_url,
                "endpoint": reverse('api:kube:cluster-admin-init', args=[self.cluster_db.cluster_id]),
                "auth_token": token
            })
        ))
        
        # Kube Cluster details
        files.append(CloudInitFile(
            path = cluster_info_file_path,
            content = json.dumps(
                self.generate_cluster_deploy_details(
                    controller_ip, 
                    self.cluster_db.cluster_id, 
                    kubernetes_version
                )
            )
        ))

        # Kubeadm template file
        path = apps.get_app_config('kube').path
        logger.debug(f"Path: {path}")
        with open(f"{path}/kubeadm_templates/init_cluster_template.yaml") as f:
            files.append(CloudInitFile(
                path = kubeadm_template_path,
                content = f.read()
            ))

        with open(f"{path}/cloudinit_scripts/02-init_kube_debian.sh") as f:
            files.append(CloudInitFile(
                path = sh_script_path,
                content = f.read(),
                permissions = '0775'
            ))

        instance_tags = {
            "Name": f"{self.cluster_db.cluster_id}-controller",
            "cluster_id": self.cluster_db.cluster_id,
            "controller": True,
        }

        # Create controller virtual machine
        vm_manager = VmManager()
        vm_id = vm_manager.create_vm(
            user, 
            instance_def=instance_def, 
            NetworkProfile = network_profile,
            ImageId = image_id,
            DiskSize = disk_size,
            PrivateIp = controller_ip,
            KeyName = key_name,
            Tags = instance_tags,
            Files = files,
            RunCommands = [sh_script_path]
        )

        # Set the primary/controller for this cluster in the database 
        self.cluster_db.primary = VirtualMachine.objects.get(instance_id=vm_id)
        self.cluster_db.save()

        return self.cluster_db.cluster_id
    

    def generate_cluster_deploy_details(self, controller_ip, cluster_id, version, cluster_svc_subnet = "10.96.0.0/12"):
        return {
            "controller_ip": controller_ip,
            "cluster_name": cluster_id,
            "cluster_version": version,
            "cluster_service_subnet": cluster_svc_subnet,
            "token_ttl": "0",
        }


    def add_node_to_cluster(self, user:User, instance_def: InstanceDefinition, node_ip:str, \
        image_id:str, network_profile:str, disk_size:str, key_name:str = None, tags:dict = None):

        tags = tags if tags else {}

        if self.cluster_db is None:
            raise ClusterConfigurationError("cluster_db is not set!")

        if self.cluster_db.status != KubeCluster.Status.READY:
            raise ClusterConfigurationError("Cluster is not in state to accept new nodes")
        
        if not self.cluster_db.primary:
            raise ClusterConfigurationError("No controller set for this cluster")
        
        controller_addr = self.cluster_db.primary.interfaces['config_at_launch']['private_ip']
        controller_addr = f"{controller_addr}:6443"

        vault = Vault()
        try:
            secrets = vault.get_secret(self.vault_mount_point, f"{user.account.account_id}/{self.cluster_db.cluster_id}")['data']['data']
        except SecretDoesNotExistError:
            raise ClusterConfigurationError("No secret data exists for primary controller. Cannot continue")

        files = []
        
        node_template_file = "/root/node.yaml"
        echome_info_file_path = "/root/server_info.yaml"
        sh_script_path = "/root/init_kube_node_debian.sh"
        
        # Create a service account and token for the controller to send
        # information back to us
        svc_acct = ServiceAccount()
        service_account = svc_acct.create_or_get(user.account)
        token = svc_acct.generate_jwt_token(service_account)

        files.append(CloudInitFile(
            path = echome_info_file_path,
            content = json.dumps({
                "server_addr": ecHomeConfig.EcHome().api_url,
                "endpoint": reverse('api:kube:cluster-admin-node-add', args=[self.cluster_db.cluster_id]),
                "auth_token": token,
            })
        ))

        # Kubeadm template file
        path = apps.get_app_config('kube').path

        with open(f"{path}/kubeadm_templates/init_node_template.yaml", 'r') as f:
            src = Template(f.read())
            result = src.substitute({
                'controller_addr': controller_addr,
                'ca_cert_hash': secrets['ca_sha'],
                'token': secrets['kubeadm_token'],
            })
            files.append(CloudInitFile(
                path = node_template_file,
                content = result
            ))
        
        with open(f"{path}/cloudinit_scripts/03-add_node_kube_debian.sh") as f:
            files.append(CloudInitFile(
                path = sh_script_path,
                content = f.read(),
                permissions = '0775'
            ))

        instance_tags = {
            "Name": f"{self.cluster_db.cluster_id}-node",
            "cluster_id": self.cluster_db.cluster_id,
            "node": True,
        }
        # Merge tags with instance_tags taking precedence
        instance_tags = {**tags, **instance_tags}

        vm_manager = VmManager()
        vm_id = vm_manager.create_vm(
            user, 
            instance_def=instance_def, 
            NetworkProfile = network_profile,
            ImageId = image_id,
            DiskSize = disk_size,
            PrivateIp = node_ip,
            KeyName = key_name,
            Tags = instance_tags,
            Files = files,
            RunCommands = [sh_script_path]
        )

        return vm_id

    
    def generate_kubernetes_image(self):
        """Creates a Kubernetes image with kubeadm that will be used to launch clusters and nodes"""
        
        pass
    
