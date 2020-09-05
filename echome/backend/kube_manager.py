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

class KubeManager:

    def create_minikube_cluster(self):
        pass

    def create_cluster(self, user:User, instance_size: Instance, \
        ips:list, image_id:str, key_name:str, network_profile:str, disk_size="50G"):

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
            'kubelauncher:0.2',
            detach=True,
            environment=[
                f"VAULT_TOKEN={config.Vault().token}",
                f"VAULT_ADDR={config.Vault().addr}",
                f"VAULT_PATH={mount}",
                f"CLUSTER_ID={cluster_id}",
                f"SSH_PRIVATE_KEY={cluster_id}",
                f"INVENTORY={inv}"
            ]
        )
    
