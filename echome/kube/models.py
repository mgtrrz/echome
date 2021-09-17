import logging
import docker
from django.db import models
from identity.models import User
from vmmanager.instance_definitions import InstanceDefinition
from vmmanager.vm_manager import VmManager
from vmmanager.models import UserKey
from echome.id_gen import IdGenerator
from echome.config import ecHomeConfig
from echome.exceptions import AttemptedOverrideOfImmutableIdException
from vault.vault import Vault

logger = logging.getLogger(__name__)

class KubeCluster(models.Model):
    cluster_id = models.CharField(max_length=20, unique=True, db_index=True)
    account = models.ForeignKey("identity.Account", on_delete=models.CASCADE, to_field="account_id", null=True)

    created = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True)
    
    type = models.CharField(max_length=50)

    class Status(models.TextChoices):
        BUILDING = 1, 'Building'
        FAILED = 2, 'Failed'
        READY = 3, 'Ready'
        UPDATING = 4, 'Updating'
        DELETING = 5, 'Deleting'
        TERMINATED = 6, 'Terminated'

    status = models.CharField(
        max_length=4,
        choices=Status.choices,
        default=Status.BUILDING,
    )

    primary = models.ForeignKey("vmmanager.VirtualMachine", \
        on_delete=models.SET_NULL, \
        to_field="instance_id", \
        related_name='primary_controller', \
        null=True)
    associated_instances = models.ManyToManyField("vmmanager.VirtualMachine")

    minimum_requirements = models.JSONField(default=dict)
    image_metadata = models.JSONField(default=dict)
    deactivated = models.BooleanField(default=False)
    tags = models.JSONField(default=dict)

    def generate_id(self):
        if self.instance_id is None or self.instane_id == "":
            self.instance_id = IdGenerator.generate("vm")
        else:
            raise AttemptedOverrideOfImmutableIdException
    
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
        ips:list, image_id:str, network_profile:str, kubernetes_version="v1.18.5", key_name=None, disk_size="50G", \
        image_user="ubuntu", image_ssh_port="22", tags={}):

        cluster_id = IdGenerator().generate("kube", 8)
        logger.debug(f"Generated cluster id {cluster_id}")
        service_key_name = IdGenerator().generate("svc-kube", 12)
        logger.debug(f"Creating Service key {service_key_name}")

        # Create a new service key for ansible to install/setup the cluster
        kstore = KeyStore()
        key = kstore.create_key(user, service_key_name, True)

        # Save the key in Vault for the Docker container to access later
        vault = Vault()
        vault.store_sshkey(self.vault_mount_point, f"{cluster_id}/svckey", key["PrivateKey"])

        # Generate the inventory file for Ansible
        logger.debug("Creating inventory file")
        inv = "[all:vars]\n"
        inv += f"ansible_user = {image_user}\n"
        inv += f"ansible_port = {image_ssh_port}\n\n"
        
        inv += "[all]\n"
        num = 1
        for ip in ips:
            inv += f"node{num} ansible_host={ip} etcd_member_name=etcd{num}\n"
            num += 1
        
        inv += "\n[kube-master]\n"
        inv += "node1\n\n"

        inv += "[etcd]\n"
        for num in range(1, len(ips)+1):
            inv += f"node{num}\n"
        
        inv += "\n[kube-node]\n"
        for num in range(2, len(ips)+1):
            inv += f"node{num}\n"

        inv += "\n[k8s-cluster:children]\n"
        inv += "kube-master\n"
        inv += "kube-node\n"

        logger.debug(inv)

        tmp_inv_file = f"/tmp/{cluster_id}_inventory.ini"
        with open(tmp_inv_file, "w") as file:
            file.write(inv)

        # Cluster yaml generation

        source_template_cluster_yaml = f"{ecHomeConfig.EcHome().base_dir}/templates/kube/k8s-cluster.yaml"
        rendered_tmp_cluster_file = f"/tmp/{cluster_id}_k8s_cluster.yaml"
        with open(source_template_cluster_yaml, "r") as template_file:
            template_contents = str.Template(template_file.read())
            cluster_yaml_render = template_contents.substitute({
                'KUBERNETES_VERSION': kubernetes_version,
                'KUBERNETES_SERVICE_ADDRESSES': "10.233.0.0/18",
                'KUBERNETES_PODS_SUBNET': "10.233.64.0/18",
                'KUBERNETES_NETWORK_NODE_PREFIX': "24",
                'KUBERNETES_CLUSTER_NAME': f"{cluster_id}.local",
            })

        with open(rendered_tmp_cluster_file, "w") as file:
            file.write(cluster_yaml_render) 

        # Generate a temporary Vault token to pass to docker
        policy_name = f"kubesvc-{cluster_id}"
        vault.create_policy(
            self._generate_vault_policy_otp(cluster_id), 
            policy_name
        )
    
        token_info = vault.generate_temp_token(
            [policy_name]
        )
        
        vmanager = VmManager()
        instances = []
        num = 1
        for ip in ips:
            if num == 1:
                name = "kube-controller"
            else:
                name = f"kube-node-{num}"

            instances.append(
                vmanager.create_vm(
                    user, 
                    instanceType=instance_size, 
                    ImageId=image_id,
                    KeyName=key_name, 
                    ServiceKey=service_key_name,
                    NetworkProfile=network_profile, 
                    DiskSize=disk_size, 
                    PrivateIp=ip,
                    Tags={
                        "Name": name,
                        "Cluster": cluster_id
                    }
                )
            )
            num += 1
        
        # Create an entry in the DB
        primary = instances[0]
        instances.pop(0)
        nodes = instances
        cluster = KubeCluster(
            cluster_id = cluster_id,
            account = user.account,
            type = "cluster",
            status = "BUILDING",
            primary_controller = primary,
            assoc_instances = nodes,
            tags = tags
        )

        cluster.commit()

        # Create a service API key for the ansible job
        # to report back to ecHome when it is complete.
        # TODO: Expiry for the service accounts
        svc_manager = ServiceAccountManager()
        auth_id, secret = svc_manager.create_service_account(user.account)
        vault.store_dict(self.vault_mount_point, f"{cluster_id}/echome", {'key': auth_id, 'secret': secret})
        
        docker_client = docker.from_env()
        docker_client.containers.run(
            'kubelauncher:0.5',
            detach=True,
            environment=[
                f"VAULT_TOKEN={token_info['auth']['client_token']}",
                f"VAULT_ADDR={ecHomeConfig.Vault().addr}",
                f"VAULT_PATH={self.vault_mount_point}",
                f"VAULT_SVC_KEY_PATH={self.vault_mount_point}/{cluster_id}/svckey",
                f"VAULT_ADMIN_PATH={self.vault_mount_point}/{cluster_id}/admin",
                f"CLUSTER_ID={cluster_id}",
                f"ECHOME_SERVER={ecHomeConfig.EcHome().api_url}",
                f"ECHOME_MSG_API=/v1/service/msg",
                f"ECHOME_AUTH_LOGIN_API=/v1/auth/api/login",
                f"ECHOME_SVC_CREDS={self.vault_mount_point}/{cluster_id}/echome",
            ],
            volumes={
                tmp_inv_file: {'bind': '/mnt/inventory.ini', 'mode': 'rw'},
                rendered_tmp_cluster_file: {'bind': '/mnt/k8s-cluster.yaml', 'mode': 'rw'},
            }
        )

        return cluster_id
    
    # otp = one time policy
    def _generate_vault_policy_otp(self, path:str):
        return """
path "kubesvc/data/%s/*" {
  capabilities = ["read", "list", "create"]
}
""" % path

class ClusterDoesNotExist(Exception):
    pass

class ServerError(Exception):
    pass