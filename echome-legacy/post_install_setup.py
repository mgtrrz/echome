from backend.database import Database
from backend.user import User
from backend.vnet import VirtualNetworkObject

# 1. Create databases
print("Creating databases..")
Database().create()
User().init_session()
VirtualNetworkObject().init_table()

# 2. Create root/primary user

# 3. Optionally add guest images