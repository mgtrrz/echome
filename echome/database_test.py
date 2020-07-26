from backend.user import User
from backend.id_gen import IdGenerator
from backend.database import dbengine
from backend.vnet import VirtualNetwork, InvalidNetworkType

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
        Name="test-network", 
        User=user, 
        Type="BridgeToLan", 
        Network="172.16.9.0", 
        Prefix="24", 
        Gateway="172.16.9.1", 
        DnsServers=["1.1.1.1", "1.0.0.1"]
    )

    print(vnet)

def use_existing_network():

    user = check_existing_user()
    network = VirtualNetwork()
    vnet = network.get_network("vnet-8719c034")

    print(vnet)
    print(vnet.config)

def delete_network():

    network = VirtualNetwork()
    vnet = network.get_network("vnet-8719c034")
    vnet.delete()


create_new_network()