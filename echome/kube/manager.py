import json
import logging
import re
import secrets
import string
import time
import yaml
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
from vmmanager.exceptions import VirtualMachineDoesNotExist
from vmmanager.instance_definitions import InstanceDefinition
from vmmanager.vm_manager import VmManager
from vmmanager.tasks import task_terminate_instance
from vmmanager.cloudinit import CloudInitFile
from vmmanager.image_manager import ImageManager
from vmmanager.models import VirtualMachine, Image
from .models import KubeCluster
from .exceptions import (
    ClusterConfigurationError, 
    ClusterDoesNotExist, 
    ClusterGetConfigurationError, 
    ClusterAlreadyExists
)
from .kubeadm_config import KubeadmInitConfig, KubeadmJoinConfig, KubeadmClusterConfig


logger = logging.getLogger(__name__)

class KubeClusterManager:

    cluster_db: KubeCluster = None
    vault_mount_point = "kube"

    def __init__(self, cluster_name:str = None, cluster_id:str = None) -> None:
        try:
            if cluster_name:
                self.cluster_db = KubeCluster.objects.get(name=cluster_name)
            elif cluster_id:
                self.cluster_db = KubeCluster.objects.get(cluster_id=cluster_id)
            else:
                self.cluster_db = KubeCluster()
        except KubeCluster.DoesNotExist:
            logger.debug("Cluster does not exist")
            raise ClusterDoesNotExist


    def _prepare_cluster_db(self, user:User, name:str, tags:dict = None):
        self.cluster_db.generate_id()
        self.cluster_db.name = name
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
        """Return the admin.conf file for the cluster"""
        vault = Vault()
        try:
            conf = vault.get_secret(
                self.vault_mount_point, 
                f"{user.account.account_id}/{self.cluster_db.cluster_id}"
            )
            conf = conf["data"]["data"]["admin.conf"]
        except Exception:
            logger.debug(f"Could not extract config from Vault for {self.cluster_db.cluster_id}/admin")
            raise ClusterGetConfigurationError("Could not retrieve config for specified cluster.")
        
        return conf
    

    def set_cluster_secrets(self, user:User, details:dict):
        """Sets a clusters secrets from the controller initialization"""
        vault = Vault()

        secrets = {
            'ca_sha': details['CaSha'],
            'admin.conf': self._make_kubeconfig_user_unique(details['AdminConf']),
        }

        vault.store_dict(
            self.vault_mount_point, 
            path_name=f"{user.account.account_id}/{self.cluster_db.cluster_id}",
            value=secrets
        )
    

    def set_cluster_token(self, user:User, token:str):
        """Sets the kubeadm token for this cluster"""
        vault = Vault()

        secrets = {
            'kubeadm_token': token
        }

        vault.store_dict(
            self.vault_mount_point, 
            path_name=f"{user.account.account_id}/{self.cluster_db.cluster_id}",
            value=secrets
        )
    

    def _make_kubeconfig_user_unique(self, kubeconfig:str) -> str:
        """ The context/user created by default is 'kubernetes-admin'. For 
        users managing multiple clusters, we'll want to make these are more unique
        so we'll use the context user with includes the cluster Id at the end.
        """
        kube_config = yaml.safe_load(kubeconfig)
        name = kube_config['contexts'][0]['name']
        kube_config['contexts'][0]['context']['user'] = name
        kube_config['users'][0]['name'] = name

        return yaml.dump(kube_config)
    

    def delete_cluster(self, user:User):
        """Terminates a Kubernetes cluster by deleting associated resources"""
        logger.debug(f"Received request to terminate cluster: {self.cluster_db.cluster_id}")
        self.cluster_db.status = KubeCluster.Status.DELETING
        self.cluster_db.save()

        # Delete Entry in Vault
        logger.debug("Deleting Vault entries for this cluster")
        vault = Vault()
        vault.delete_key(self.vault_mount_point, f"{self.cluster_db.account.account_id}/{self.cluster_db.cluster_id}")

        # Delete controller VM
        controller = self.cluster_db.primary
        if controller:
            logger.debug("Terminating controller instance")
            task_terminate_instance.delay(controller.instance_id, user.user_id)

        # Delete kube cluster by setting state to TERMINATED
        self.cluster_db.primary = None
        self.cluster_db.status = KubeCluster.Status.TERMINATED
        self.cluster_db.delete()

        return True
    

    def prepare_cluster(self, user: User, name: str, instance_def: str, \
        controller_ip:str, network_profile:str, kubernetes_version:str, 
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

        # Check to see if this cluster name already exists for this account
        try:
            c = KubeCluster.objects.exclude(status=KubeCluster.Status.TERMINATED).get(name=name, account=user.account)
            if c:
                raise ClusterAlreadyExists
        except KubeCluster.DoesNotExist:
            pass
        except ClusterAlreadyExists:
            raise
        except Exception as e:
            logger.exception(e)
            raise

        if not self.kubernetes_version_is_valid(kubernetes_version):
            raise ClusterConfigurationError("Kubernetes version is not valid")

        # Checking inputs to make sure everything is correct
        try:
            InstanceDefinition(instance_def)
            network = VirtualNetworkManager(network_profile, user)
            network.validate_ip(controller_ip)
            if key_name:
                UserKeyManager(key_name, user)
        except Exception as e:
            logger.exception(e)
            raise ClusterConfigurationError
        
        # Check to see if we already have a prepared image for this version
        images = Image.objects.filter(
            tags__has_key='ecHome_kubernetes__image', 
            tags__contains={'ecHome_kubernetes__version': kubernetes_version}
        )
        if not images:
            raise ClusterConfigurationError("No prepared Kubernetes images exist for specified version. \
                    Please create a new Kubernetes prepared image for this Kubernetes version.")

        cluster_id = self._prepare_cluster_db(user, name, tags=tags)
        return cluster_id


    def create_cluster(self, user:User, instance_def: InstanceDefinition, \
        controller_ip:str, network_profile:str, disk_size:str, kubernetes_version:str, 
        key_name:str = None):
        """Creates a new Kubernetes cluster with a primary controller. The function creates an instance then 
        uses UserData scripts to add files onto the cluster for kubeadm to initialize."""

        if self.cluster_db is None:
            raise ClusterConfigurationError("cluster_db is not set!")
        
        images = Image.objects.filter(
            tags__has_key='ecHome_kubernetes__image', 
            tags__contains={'ecHome_kubernetes__version': kubernetes_version}
        )
        if not images:
            raise ClusterConfigurationError("No prepared images exist for this Kubernetes version.")
        
        logger.debug(f"Using image: {images[0]}")

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

        logger.debug("Generating Kubeadm token..")
        kubeadm_token = self.generate_kubeadm_token()

        # Save this token in Vault
        self.set_cluster_token(user, kubeadm_token)

        # Kubeadm template file
        kubeadm_init_config = KubeadmInitConfig(
            version = kubernetes_version,
            kubeadm_token = kubeadm_token,
            controller_ip = controller_ip,
            hostname = self.cluster_db.cluster_id,
        )

        kubeadm_cluster_config = KubeadmClusterConfig(
            version = kubernetes_version,
            cluster_name = self.cluster_db.cluster_id,
        )

        logger.debug("Generated the Kubeadm config files:")
        logger.debug(kubeadm_init_config.generate_yaml())
        logger.debug(kubeadm_cluster_config.generate_yaml())

        # Write kubeadm config files
        files.append(CloudInitFile(
            path = "/root/kube_init.yaml",
            content = kubeadm_init_config.generate_yaml(
                additional_documents = [kubeadm_cluster_config.generate_document()]
            )
        ))

        # write cluster bootstrap script
        path = apps.get_app_config('kube').path
        logger.debug(f"Path: {path}")
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
            ImageId = images[0].image_id,
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
    

    def add_node_to_cluster(self, user:User, instance_def: InstanceDefinition, node_ip:str, \
        image_id:str, network_profile:str, disk_size:str, key_name:str = None, tags:dict = None):
        """Adds a node to an existing cluster. This will create an instance, add the UserData scripts and use
        kubeadm to join the primary controller in the cluster."""

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


    def generate_kubeadm_token(self):
        # https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-token/
        # [a-z0-9]{6}.[a-z0-9]{16}
        return f"{self.gen_secret_string(6)}.{self.gen_secret_string(16)}"


    def gen_secret_string(self, length:int) -> str:
        return ''.join(
            secrets.choice(
                string.ascii_lowercase + string.digits
            ) for _ in range(length)
        )


    def kubernetes_version_is_valid(self, kubernetes_version:str):
        pattern = re.compile("^(\d+)\.(\d+)$")
        return True if pattern.match(kubernetes_version) else False

    
    def generate_kubernetes_image(self, user:User, base_image:str, network_profile:str, kubernetes_version:str, key_name:str = None):
        """Creates a Kubernetes base image with kubeadm that will be used to launch clusters and nodes.
        This launches a Virtual Machine. Once the VM is complete, sends a message back to us if it was successful
        then shuts down to create the base image."""

        # TODO: Create a JobToken to authenticate requests where we're waiting for an instance to complete
        # a job.

        if not self.kubernetes_version_is_valid(kubernetes_version):
            raise ClusterConfigurationError("Kubernetes version is not valid")

        files = []

        # Init template
        path = apps.get_app_config('kube').path
        logger.debug(f"Path: {path}")

        with open(f"{path}/cloudinit_scripts/01-prepare_kube_image_debian.sh", 'r') as f:
            files.append(CloudInitFile(
                path = "/root/init_prepare_kubernetes.sh",
                content = f.read(),
                permissions = '0775'
            ))
        
        # Create a service account and token for the image to send
        # information back to us
        svc_acct = ServiceAccount()
        service_account = svc_acct.create_or_get(user.account)
        token = svc_acct.generate_jwt_token(service_account)

        files.append(CloudInitFile(
            path = "/root/server_info.yaml",
            content = json.dumps({
                "server_addr": ecHomeConfig.EcHome().api_url,
                "endpoint": reverse('api:kube:cluster-admin-prepare'),
                "auth_token": token,
            })
        ))

        files.append(CloudInitFile(
            path = "/root/kube_version",
            content = str(kubernetes_version)
        ))

        tags = {
            "echome_managed": True, 
            "ephemeral": True, 
            "kubernetes_version": kubernetes_version
        }

        vm_manager = VmManager()
        vm_id = vm_manager.create_vm(
            user, 
            instance_def=InstanceDefinition("standard", "nano"), 
            NetworkProfile = network_profile,
            ImageId = base_image,
            DiskSize = "10G",
            Tags = tags,
            Files = files,
            KeyName = key_name,
            RunCommands = ["/root/init_prepare_kubernetes.sh"]
        )


    def register_kubernetes_image(self, user:User, instance_id:str):
        """Registers a Virtual Machine Image (vmi) for Kubernetes created by the generate_kubernetes_image function.
        These images will be used for creating Kubernetes clusters"""
        vm_manager = VmManager()

        try:
            vm_db = vm_manager.get_vm_db_from_id(instance_id)
        except VirtualMachineDoesNotExist:
            logger.debug("Did not find VM with this instance ID")
            raise
        
        if user.account != vm_db.account:
            logger.debug("Requested user or service account does not have permission to this virtual machine.")
            raise VirtualMachineDoesNotExist
        
        image_name = vm_db.image_metadata['image_name']
        image_id = vm_db.image_metadata['image_id']
        kube_ver = vm_db.tags['kubernetes_version']

        build_time = str(int(time.time()))

        vmi_tags = {
            "ecHome_kubernetes__image": "",
            "ecHome_kubernetes__base_image_id": image_id,
            "ecHome_kubernetes__version": kube_ver,
            "echome_kubernetes__build_date": build_time
        }

        try:
            vmi = vm_manager.create_virtual_machine_image(
                vm_id = instance_id,
                user = user,
                name = f"kubernetes-image-{kube_ver}",
                description = f"ecHome-Kubernetes base image from {image_name} ({image_id}) - {build_time}",
                tags = vmi_tags,
                terminate_after_creation = True
            )
        except Exception as e:
            logger.exception(e)
            raise

