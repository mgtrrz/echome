from backend.user import User
from backend.id_gen import IdGenerator
from backend.database import dbengine
from backend.vnet import VirtualNetwork, InvalidNetworkType
from backend.vm_manager import VmManager
from backend.instance_definitions import Instance
import json
import logging

logging.basicConfig(level=logging.DEBUG)

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


def create_vm():
    user = check_existing_user()
    vmanager = VmManager()
    id = vmanager.create_vm(
        user, 
        Instance("standard", "micro"), 
        NetworkProfile="home-network",
        ImageId="gmi-07b7e1e4",
        KeyName="echome",
        DiskSize="10G",
        PrivateIp="172.16.9.30",
        Tags={"Name": "Test-deployment", "Environment": "Test"}
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

    


create_vm()