import libvirt
import sys
from vm_manager import vmManager
from database import Database
from ssh_keystore import EchKeystore
from instance_definitions import Instance
import logging

logging.basicConfig(level=logging.DEBUG)

conn = libvirt.openReadOnly(None)
if conn == None:
    print('Failed to open connection to the hypervisor')
    sys.exit(1)


domainIDs = conn.listDomainsID()
if domainIDs == None:
    print('Failed to get a list of domain IDs', file=sys.stderr)

print("Active domain IDs:")
if len(domainIDs) == 0:
    print('  None')
else:
    for domainID in domainIDs:
        print('  '+str(domainID))

conn.close()

###

db = Database("./database.ini")

keystore = EchKeystore()
user = {
    "account_id": "12345",
    "account_user_id": "11119",
}
#keystore.store_key(db, user, "test_key", "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCeKJ9F5NyjxFKWBgBQFiQHofsoFi46Q2Yer0RdiuqyUusxsIzSyv+ZkWM2WuZ0V10oBC/oS0S1moVqREPUJBo5RRtwEHmTOloAy/sAMA30A58xpTbW9BjVb1Y3XxMHLnkgo5dYn1Y9P7ROrWG+sXRlfao9jYhOpEiuqif232DzSj982FVboRUO57tCAedHZFpwEUHUQDXX7hfu7x09YqHKTWW2CkH+DNwckY/90sRynY/OX9fpXLYwOgDFPP+vZas9PEGL8YNWikGyct84Dv3yYsLn9NsnleT71uXNtbE74LnvGtAUvhaKEVdO+Os5eU49pI2MDObGipQ+qpEw4zQ5 mark@Marcuss-MacBook-Pro.local")
#print(keys)

vmHost = vmManager()
instanceType = Instance("standard", "small")
cloudinit_params = {
    "cloudinit_key": keystore.get_key(db, user, "test_key"),
    "network": "local", # local, private, public?
    "private_ip": "172.16.9.10/24"
}
vmHost.createInstance(instanceType, cloudinit_params)