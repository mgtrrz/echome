import libvirt
import sys
import json
from vm_manager import vmManager
from database import Database
from ssh_keystore import EchKeystore
from instance_definitions import Instance
from guest_image import GuestImage
import logging

logging.basicConfig(level=logging.DEBUG)

# Basic user account for testing
user = {
    "account_id": "12345",
    "account_user_id": "11119",
}

vmHost = vmManager()

metadata = vmHost.getInstanceMetaData(user, "vm-b49c2840")
print(metadata)

# Example Instance definition
instanceType = Instance("standard", "small")

# Example ssh key definition
key_meta = EchKeystore().get_key(user, "test_key")
print(key_meta)

cloudinit_params = {
    "cloudinit_key_name": key_meta[0]["key_name"],
    "cloudinit_public_key": key_meta[0]["public_key"],
    "network": "BridgeToLan", # local, private, public?
    "private_ip": "172.16.9.13/24",
    "gateway_ip": "172.16.9.1"
}
server_params = {
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

# img_data = GuestImage().getImageMeta("gmi-fc1c9a62")
# print(json.dumps(img_data, indent=4))

#GuestImage().registerImage("/data/ssd_storage/guest_images/windows_server_2012_r2_standard_eval_kvm_20170321.qcow2", "Windows Server 2020 R2 Standard Eval 64-bit", "Cloud image provided by cloudbase.it/windows-cloud-images/")