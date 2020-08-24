import time
import logging
import ipaddress
import string
import docker
from backend.id_gen import IdGenerator
from backend.user import UserManager
from backend.vm_manager import VmManager
from backend.ssh_keystore import KeyStore
from backend.instance_definitions import Instance
from backend.vault import Vault

class KubeManager:

    def create_minikube_cluster(self):
        pass

    def create_cluster(self):

        user = UserManager().get_user(user_id="user-d4193166")
        cluster_id = IdGenerator().generate("kube", 8)
        service_key_name = IdGenerator().generate("svc-kube", 12)
        logging.debug(f"Creating Service key {service_key_name}")

        # Create a new service key for ansible to install/setup the cluster
        kstore = KeyStore()
        key = kstore.create_key(user, service_key_name, True)

        # Save the key in Vault for the Docker container to access later
        vault = Vault()
        vault.store_sshkey(cluster_id, key["PrivateKey"])

        # Create instances
        instance_size = "standard.medium"
        ips = ["172.16.9.20", "172.16.9.21", "172.16.9.22"]
        
        vmanager = VmManager()
        num = 1
        for ip in ips:
            vmanager.create_vm(user, 
                instanceType=Instance("standard", "medium"), 
                ImageId="gmi-d8cacd92",
                KeyName="echome", 
                ServiceKey=service_key_name,
                NetworkProfile="home-network", 
                DiskSize="50G", 
                PrivateIp=ip,
                Tags={
                    "Name": f"kubernetes-{num}",
                    "Cluster": cluster_id
                }
            )
            num = num + 1
