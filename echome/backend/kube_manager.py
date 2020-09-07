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

    id = Column(Integer, primary_key=True)
    cluster_id = Column(String(20), unique=True)
    account = Column(String(20), nullable=False)
    created = Column(DateTime(), nullable=False, server_default=func.now())
    type = Column(String())
    primary_controller = Column(String())
    assoc_instances = Column(JSONB)
    tags = Column(JSONB)

    def init_session(self):
        self.session = dbengine.return_session()
        return self.session

    def commit(self):
        self.session.commit()

    def add(self):
        self.session.add(self)
        self.session.commit()

    def __str__(self):
        return self.cluster_id

class KubeManager:

    def create_minikube_cluster(self):
        pass

    def create_cluster(self, user:User, instance_size: Instance, \
        ips:list, image_id:str, key_name:str, network_profile:str, disk_size="50G", \
        image_user="ubuntu", image_ssh_port="22"):

        cluster_id = IdGenerator().generate("kube", 8)
        service_key_name = IdGenerator().generate("svc-kube", 12)
        logging.debug(f"Creating Service key {service_key_name}")

        # Create a new service key for ansible to install/setup the cluster
        kstore = KeyStore()
        key = kstore.create_key(user, service_key_name, True)

        # Save the key in Vault for the Docker container to access later
        mount = "kubesvc"
        vault = Vault()
        vault.store_sshkey(mount, f"{cluster_id}/svckey", key["PrivateKey"])

        # Generate the inventory file for Ansible
        logging.debug("Creating inventory file")
        inv = "[all:vars]\n"
        inv += f"ansible_user = {image_user}\n"
        inv += f"ansible_port = {image_ssh_port}\n\n"
        
        inv += "[all]\n"
        num = 1
        for ip in ips:
            inv += f"node{num} ansible_host={ip} etcd_member_name=etcd{num}\n"
        
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
        num = 1
        for ip in ips:
            if num == 1:
                name = "kubernetes-controller"
            else:
                name = f"kube-node-{num}"

            vmanager.create_vm(user, 
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
            num += 1
        
        config = AppConfig()
        docker_client = docker.from_env()
        docker_client.containers.run(
            'kubelauncher:0.3',
            detach=True,
            environment=[
                f"VAULT_TOKEN={token_info['auth']['client_token']}",
                f"VAULT_ADDR={config.Vault().addr}",
                f"VAULT_PATH={mount}",
                f"CLUSTER_ID={cluster_id}",
                f"SSH_PRIVATE_KEY={cluster_id}",
                f"INVENTORY={inv}"
            ]
        )
    
    # otp = one time policy
    def _generate_vault_policy_otp(self, path:str):
        return """
path "kubesvc/%s" {
  capabilities = ["read", "list", "create"]
}
""" % path
    
