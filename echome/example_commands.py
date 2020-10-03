from backend.user import UserManager, User
from backend.id_gen import IdGenerator
from backend.database import dbengine
from backend.vnet import VirtualNetwork, InvalidNetworkType
from backend.vm_manager import VmManager
from backend.instance_definitions import Instance
from backend.kube_manager import KubeManager
from backend.guest_image import ImageManager
import json
import logging

#logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()
logger.setLevel(level=logging.DEBUG)

# user.init_session()
# for user in session.query(user).filter_by(username='marknine'):
#     print(user)

####################################
# Initializing a SQLAlchemy session (https://docs.sqlalchemy.org/en/13/orm/session_basics.html)
# Entry-point 
# Create one session!

# from backend.database import dbengine
# dbengine.session!



# user = dbsession.query(User).filter_by(auth_id="auth-d4193167").first()
# print(user)

# user.set_server_secret()
# dbsession.add(user)
# dbsession.commit()

# user.init_session()
# user.add()

script = """#!/bin/bash
echo "Hello World.  The time is now $(date -R)!" | tee /root/output.txt
"""


def create_vm():
    user = check_existing_user()
    vmanager = VmManager()
    id = vmanager.create_vm(
        user, 
        Instance("standard", "small"), 
        NetworkProfile="home-network",
        ImageId="gmi-07b7e1e4",
        KeyName="echome",
        DiskSize="50G",
        PrivateIp="172.16.9.12",
        Tags={"Name": "RemoteDevServer", "Environment": "Dev"},
        UserDataScript=script
    )
    print(id)


def check_existing_user():
    #################
    # Working with an existing user
    user = dbengine.session.query(User).filter_by(user_id="user-d4193166").first()
    print(user)
    return user

def create_user():
    #################
    # Creating a user
    user = User(
        user_id=IdGenerator.generate("user"),
        primary=True,
        account="12345",
        username="marknine",
        name="Marcus Gutierrez"
    )

    # # Setting a password
    user.set_password("MyPassword")
    dbengine.session.add(user)
    dbengine.session.commit()

    # Create API client and secret for this user
    user_api_obj, secret_token = user.create_api_auth()
    dbengine.session.add(user_api_obj)
    dbengine.session.commit()
    print(secret_token)

    # Checking to see if the password or secret match
    print(user.check_password("MyPassword"))

def get_users():
    user = check_existing_user()
    uman = UserManager()
    users = uman.get_all_users(user.account)
    for user in users:
        print(user)


def create_new_network():

    user = check_existing_user()

    network = VirtualNetwork()
    vnet = network.create(
        Name="home-network", 
        User=user, 
        Type="BridgeToLan", 
        Network="172.16.9.0", 
        Prefix="24", 
        Gateway="172.16.9.1", 
        DnsServers=["1.1.1.1", "1.0.0.1"],
        Bridge="br0"
    )

    print(vnet)

def use_existing_network():

    user = check_existing_user()
    network = VirtualNetwork()
    vnet = network.get_network("vnet-517d0ed2", user)

    print(vnet)
    print(vnet.config)

def delete_network():
    user = check_existing_user()
    network = VirtualNetwork()
    vnet = network.get_network("vnet-517d0ed2", user)
    vnet.delete()

def check_networking():
    # See if we can create an IP in this network space
    user = check_existing_user()
    network = VirtualNetwork()
    
    vnets = network.get_all_networks(user)
    response = []
    for vnet in vnets:
        response.append({
            "network_id": vnet.vnet_id,
            "name": vnet.profile_name,
            "type": vnet.type,
            "created": str(vnet.created),
            "config": vnet.config,
            "tags": vnet.tags,
        })
    
    print(json.dumps(response, indent=4))


def create_kube_cluster():
    user = check_existing_user()
    kmanager = KubeManager()
    kmanager.create_cluster(
        user=user,
        instance_size=Instance("standard", "medium"),
        ips=["172.16.9.20", "172.16.9.21", "172.16.9.22"],
        image_id="gmi-d8cacd92",
        key_name="echome",
        network_profile="home-network"
    )

def update_kube_cluster():
    user = check_existing_user()
    kmanager = KubeManager()
    cluster = kmanager.get_cluster_by_id("kube-3a0be876")
    cluster.assoc_instances = ["vm-3b0120e8", "vm-3b0120e9"]
    cluster.commit()

def delete_kube_cluster():
    user = check_existing_user()
    kmanager = KubeManager()
    kmanager.delete_cluster("kube-3a0be876", user)

def get_all_clusters():
    user = check_existing_user()
    Kmanager = KubeManager()
    clusters = Kmanager.get_all_clusters(user)
    for cluster in clusters:
        print(cluster)

def get_cluster_config():
    user = check_existing_user()
    Kmanager = KubeManager()
    conf = Kmanager.get_cluster_config("kube-9206ef78", user)
    print(conf)

def get_images():
    user = check_existing_user()
    manager = ImageManager()
    print("Guest images: ")
    images = manager.getAllImages("guest")
    for image in images:
        print(image)
        
    print("\nUser images: ")
    images = manager.getAllImages("user", user)
    for image in images:
        print(image)


get_users()
