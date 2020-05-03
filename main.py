import libvirt
import sys
from vm_manager import vmManager
from database import Database
from ssh_keystore import EchKeystore
from instance_definitions import Instance
import logging

logging.basicConfig(level=logging.DEBUG)

###

db = Database("./database.ini")

keystore = EchKeystore()
user = {
    "account_id": "12345",
    "account_user_id": "11119",
}
#keystore.store_key(db, user, "test_key", "<ssh-key>")
#print(keys)

vmHost = vmManager()
instanceType = Instance("standard", "small")

cloudinit_params = {
    "cloudinit_key": keystore.get_key(db, user, "test_key"),
    "network": "local", # local, private, public?
    "private_ip": "172.16.9.12/24",
    "gateway_ip": "172.16.9.1"
}
server_params = {
    "image": "ubuntu-18.04-server-cloudimg-amd64.img",
    #"vmi": "vmi-293de.qcow2",
    "disk_size": "10G",
}
#vmHost.createInstance(instanceType, cloudinit_params, server_params)
#vmHost.stop_vm("vm-04a800da")
#vmHost.terminateInstance("vm-c947f642")

vmHost.createVirtualMachineImage(user["account_id"], "vm-5946343e", "ubuntu-18.04-server-cloudimg-amd64.img")