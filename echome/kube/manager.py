import logging
import json
from django.apps import apps
from django.urls import reverse
from echome.config import ecHomeConfig
from identity.models import User
from identity.manager import ServiceAccount
from vault.vault import Vault
from network.manager import VirtualNetworkManager
from keys.manager import UserKeyManager
from vmmanager.instance_definitions import InstanceDefinition
from vmmanager.vm_manager import VmManager
from vmmanager.cloudinit import CloudInitFile
from vmmanager.image_manager import ImageManager
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
    

    def delete_cluster(self, cluster_id:str, user:User):
        # TODO: This
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
        service_account = svc_acct.create(user.account)
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
            template_file = CloudInitFile(
                path = kubeadm_template_path,
                content = f.read()
            )
            files.append(template_file)

        with open(f"{path}/cloudinit_scripts/02-init_kube_debian.sh") as f:
            init_kube_script = CloudInitFile(
                path = sh_script_path,
                content = f.read(),
                permissions = '0775'
            )
            files.append(init_kube_script)

        instance_tags = {
            "Name": f"{self.cluster_db.cluster_id}-controller",
            "cluster_id": self.cluster_db.cluster_id,
            "controller": True,
        }

        # Create controller virtual machine
        vm_manager = VmManager()
        vm_manager.create_vm(user, instance_def=instance_def, 
            NetworkProfile = network_profile,
            ImageId = image_id,
            DiskSize = disk_size,
            PrivateIp = controller_ip,
            KeyName = key_name,
            Tags = instance_tags,
            Files = files,
            RunCommands = [sh_script_path]
        )

        return self.cluster_db.cluster_id
    

    def generate_cluster_deploy_details(self, controller_ip, cluster_id, version, cluster_svc_subnet = "10.96.0.0/12"):
        return {
            "controller_ip": controller_ip,
            "cluster_name": cluster_id,
            "cluster_version": version,
            "cluster_service_subnet": cluster_svc_subnet,
            "token_ttl": "1h0m0s",
        }

    
    def generate_kubernetes_image(self):
        """Creates a Kubernetes image with kubeadm that will be used to launch clusters."""
        
        pass
    
