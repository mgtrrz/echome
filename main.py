import libvirt
import sys
import json
from vm_manager import vmManager
from database import Database
from ssh_keystore import EchKeystore
from instance_definitions import Instance
#from guest_image import GuestImage
import logging

logging.basicConfig(level=logging.DEBUG)

user = {
    "account_id": "12345",
    "account_user_id": "11119",
}

vmHost = vmManager()
print("--all--instances---")
instances = vmHost.getAllInstances(user)
print(json.dumps(instances, indent=4))

print("--specific--instance---")
results = vmHost.getInstanceMetaData(user, "vm-a8b30fda")
print(results)

instanceType = Instance("standard", "small")


key_meta = EchKeystore().get_key(user, "test_key")

cloudinit_params = {
    "cloudinit_key_name": key_meta["key_name"],
    "cloudinit_public_key": key_meta["public_key"],
    "network": "local", # local, private, public?
    "private_ip": "172.16.9.13/24",
    "gateway_ip": "172.16.9.1"
}
server_params = {
    # ubuntu-18.04-server-cloudimg-amd64.img
    "image_id": "gmi-fc1c9a62",
    #"vmi": "vmi-293de.qcow2",
    "disk_size": "10G",
}
tags = {
    "Name": "examplename",
    "org": "Testorg",
    "env": "sandbox",
    "type": "Random type, maybe kubernetes?"
}
#print(cloudinit_params)

#instance_data = vmHost.createInstance(user, instanceType, cloudinit_params, server_params, tags)
#print(instance_data["meta_data"]["vm_id"])