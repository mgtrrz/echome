import time
import logging
import ipaddress
import string
import docker
from backend.id_gen import IdGenerator
from backend.config import AppConfig
from backend.user import UserManager, User
from backend.vm_manager import VmManager
from backend.ssh_keystore import KeyStore
from backend.instance_definitions import Instance
from backend.vault import Vault
from .database import dbengine
from sqlalchemy import select, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Table, Column, Integer, String, \
    MetaData, DateTime, TEXT, ForeignKey, create_engine, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import select, func

Base = declarative_base()

class KubeCluster(Base):
    __tablename__ = "kube_clusters"
    metadata = MetaData()

    id = Column(Integer, primary_key=True)
    cluster_id = Column(String(20), unique=True)
    account = Column(String(20), nullable=False)
    created = Column(DateTime(), nullable=False, server_default=func.now())
    type = Column(String())
    status = Column(String(50))
    last_status_update = Column(DateTime(), nullable=False, server_default=func.now())
    primary_controller = Column(String())
    assoc_instances = Column(JSONB)
    cluster_metadata = Column(JSONB)
    tags = Column(JSONB)

    def commit(self):
        dbengine.session.add(self)
        dbengine.session.commit()
    
    # Delete this object from the database
    def delete(self):
        dbengine.session.delete(self)
        dbengine.session.commit()

    def __str__(self):
        return self.cluster_id

class KubeManager:

    vault_mount_point = "kubesvc"

    def create_minikube_cluster(self):
        pass

    def get_cluster_by_id(self, cluster_id:str, user:User):
        return dbengine.session.query(KubeCluster).filter_by(
                cluster_id=cluster_id,
                account=user.account
            ).first()

    def get_all_clusters(self, user:User):
        return dbengine.session.query(KubeCluster).filter_by(
                account=user.account
            ).all()

    def process_cluster_update(self, cluster_id:str, msg:str):
        cluster = self.get_cluster_by_id(cluster_id)
        if not cluster:
            raise ClusterDoesNotExist()
        
    statuses = ("BUILDING", "FAILED", "READY", "UPDATING", "DELETING", "TERMINATED")
    def update_cluster_status(self, cluster:KubeCluster, status:str):
        if status not in self.statuses:
            raise ValueError("Provided status is not in list of statuses for KubeCluster")
        cluster.status == status
        cluster.commit()

    def get_cluster_config(self, cluster_id:str, user:User):
        cluster = dbengine.session.query(KubeCluster).filter_by(
                cluster_id=cluster_id,
                account=user.account
            ).first()

        if not cluster:
            logging.debug(f"Could not get specified cluster id")
            raise ClusterDoesNotExist()

        vault = Vault()
        try:
            conf = vault.get_secret(self.vault_mount_point, f"{cluster_id}/admin")
            conf = conf["data"]["data"]["admin.conf"]
        except Exception:
            logging.debug(f"Could not extract config from Vault for {cluster_id}/admin")
            raise ServerError("Could not retrieve config for specified cluster.")
        
        return conf

    def delete_cluster(self, cluster_id:str, user:User):

        cluster = self.get_cluster_by_id(cluster_id, user)
        if not cluster:
            raise ClusterDoesNotExist()

        self.update_cluster_status(cluster, "DELETING")

        vmanager = VmManager()
        logging.debug(f"Terminating primary controller: {cluster.primary_controller}")
        vmanager.terminateInstance(user, cluster.primary_controller)
        logging.debug("Terminating nodes..")
        for inst in cluster.assoc_instances:
            logging.debug(f"..node {inst}")
            vmanager.terminateInstance(user, inst)

        # Delete Vault entries
        vault = Vault()
        vault.client.sys.delete_policy(f"kubesvc-{cluster_id}")

        vault.delete_key(mount_point=self.vault_mount_point, path_name=cluster_id)
        
        cluster.delete()
        return True


    def create_cluster(self, user:User, instance_size: Instance, \
        ips:list, image_id:str, network_profile:str, key_name=None, disk_size="50G", \
        image_user="ubuntu", image_ssh_port="22", tags={}):

        cluster_id = IdGenerator().generate("kube", 8)
        logging.debug(f"Generated cluster id {cluster_id}")
        service_key_name = IdGenerator().generate("svc-kube", 12)
        logging.debug(f"Creating Service key {service_key_name}")

        # Create a new service key for ansible to install/setup the cluster
        kstore = KeyStore()
        key = kstore.create_key(user, service_key_name, True)

        # Save the key in Vault for the Docker container to access later
        vault = Vault()
        vault.store_sshkey(self.vault_mount_point, f"{cluster_id}/svckey", key["PrivateKey"])

        # Generate the inventory file for Ansible
        logging.debug("Creating inventory file")
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

        logging.debug(inv)

        tmpfile = f"/tmp/{cluster_id}_inventory.ini"
        with open(tmpfile, "w") as file:
            file.write(inv)


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
        
        config = AppConfig()
        docker_client = docker.from_env()
        docker_client.containers.run(
            'kubelauncher:0.4',
            detach=True,
            environment=[
                f"VAULT_TOKEN={token_info['auth']['client_token']}",
                f"VAULT_ADDR={config.Vault().addr}",
                f"VAULT_PATH={self.vault_mount_point}",
                f"CLUSTER_ID={cluster_id}",
                f"SSH_PRIVATE_KEY={cluster_id}"
            ],
            volumes={
                tmpfile: {'bind': '/mnt/inventory.ini', 'mode': 'rw'},
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