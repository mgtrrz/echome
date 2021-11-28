import logging
from identity.models import User
from vault.vault import Vault
from vmmanager.instance_definitions import InstanceDefinition
from vmmanager.vm_manager import VmManager
from vmmanager.cloudinit import CloudInitFile
from .models import KubeCluster

logger = logging.getLogger(__name__)

class KubeClusterManager:

    cluster_db: KubeCluster = None

    def __init__(self, cluster_id:str = None) -> None:
        if cluster_id:
            self.cluster_db = KubeCluster(cluster_id=cluster_id)
        else:
            self.cluster_db = KubeCluster()


    def prepare_cluster(self, tags:dict = None):
        self.cluster_db.generate_id()
        self.cluster_db.tags = tags if tags else {}
        self.cluster_db.save()
        return self.cluster_db.cluster_id
    

    def get_cluster_config(self, cluster_id:str, user:User):

            vault = Vault()
            try:
                conf = vault.get_secret(self.vault_mount_point, f"{cluster_id}/admin")
                conf = conf["data"]["data"]["admin.conf"]
            except Exception:
                logger.debug(f"Could not extract config from Vault for {cluster_id}/admin")
                raise ServerError("Could not retrieve config for specified cluster.")
            
            return conf
    
    def delete_cluster(self, cluster_id:str, user:User):

        cluster = self.get_cluster_by_id(cluster_id, user)
        if not cluster:
            raise ClusterDoesNotExist()

        self.status = self.Status.DELETING

        vmanager = VmManager()
        logger.debug(f"Terminating primary controller: {cluster.primary_controller}")
        vmanager.terminateInstance(user, cluster.primary_controller)
        logger.debug("Terminating nodes..")
        for inst in cluster.assoc_instances:
            logger.debug(f"..node {inst}")
            vmanager.terminateInstance(user, inst)

        # Delete Vault entries
        vault = Vault()
        vault.client.sys.delete_policy(f"kubesvc-{cluster_id}")
        vault.delete_kv_dir(mount_point=self.vault_mount_point, path_name=cluster_id)
        
        cluster.delete()
        return True


    def create_cluster(self, user:User, instance_size: InstanceDefinition, \
        controller_ip:str, image_id:str, network_profile:str, kubernetes_version:str = "1.22", 
        key_name:str = None, disk_size:str = "50G", tags:dict = None):

        cluster_db = KubeCluster()
        cluster_db.generate_id()
        logger.debug(f"Generated cluster id {cluster_db.cluster_id}")

        files = []

        sh_script = '/root/init_kube_debian.sh'
        
        # Cluster deploy JSON details
        deploy_details = self.generate_cluster_deploy_details(
            controller_ip, cluster_db.cluster_id, kubernetes_version)
        cluster_file = CloudInitFile(
            path = "/root/cluster_info.yaml",
            content = deploy_details
        )
        files.append(cluster_file)

        # Kubeadm template file
        with open("./kubeadm_templates/init_cluster_template.yaml") as f:
            template_file = CloudInitFile(
                path = "/root/kubeadm_template.yaml",
                content = f.read()
            )
            files.append(template_file)

        with open("./cloudinit_scripts/02-init_kube_debian.sh") as f:
            init_kube_script = CloudInitFile(
                path = sh_script,
                content = f.read(),
                permissions = '0775'
            )
            files.append(init_kube_script)


        instance_tags = {
            "Name": f"{cluster_db.cluster_id}-controller",
            "cluster_id": cluster_db.cluster_id,
            "controller": True,
        }

        # Create controller virtual machine
        vm_manager = VmManager()
        vm_manager.create_vm(user, instance_size, 
            NetworkProfile = network_profile,
            ImageId = image_id,
            DiskSize = disk_size,
            PrivateIp = controller_ip,
            KeyName = key_name,
            Tags = instance_tags,
            Files = files,
            RunCommands = [sh_script]
        )

        return cluster_db.cluster_id
    

    def generate_cluster_deploy_details(self, controller_ip, cluster_id, version, cluster_svc_subnet = "10.96.0.0/12"):
        return {
            "controller_ip": controller_ip,
            "cluster_name": cluster_id,
            "cluster_version": version,
            "cluster_service_subnet": cluster_svc_subnet,
            "token_ttl": "0h1m0s",
        }

    
    def generate_kubernetes_image(self):
        """Creates a Kubernetes image with kubeadm that will be used to launch clusters."""
        
        pass
    
    # otp = one time policy
    def _generate_vault_policy_otp(self, path:str):
        return """
path "kubesvc/data/%s/*" {
  capabilities = ["read", "list", "create"]
}
""" % path

