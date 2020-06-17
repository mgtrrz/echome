import libvirt
import sys
import json
import logging
from backend.vm_manager import VmManager
from backend.ssh_keystore import EchKeystore
from backend.instance_definitions import Instance
from backend.guest_image import GuestImage, UserImage
from backend.config import AppConfig

# config = AppConfig()
# basedir = config.get_app_base_dir()
# print(basedir)

# print(config.echome["base_dir"])

logging.basicConfig(level=logging.DEBUG)

# Basic user account for testing
user = {
    "account_id": "12345",
    "account_user_id": "11119",
}

#vmHost = VmManager()
#vmHost.terminateInstance(user, "vm-1cde03da")
#vmHost.createVirtualMachineImage(user, "vm-ca065ed2")

# metadata = vmHost.getInstanceMetaData(user, "vm-b49c2840")
# print(metadata)

# Example Instance definition
# instanceType = Instance("standard", "small")

# Example ssh key definition
#key_meta = EchKeystore().get_key(user, "echome")

# cloudinit_params = {
#     "cloudinit_key_name": key_meta[0]["key_name"],
#     "cloudinit_public_key": key_meta[0]["public_key"],
#     "network_type": "BridgeToLan", # local, private, public?
#     "private_ip": "172.16.9.13/24",
#     "gateway_ip": "172.16.9.1",
#     "vm_id": "vmkdmkd"
# }
# server_params = {
#     "image_id": "gmi-fc1c9a62",
#     #"vmi": "vmi-293de.qcow2",
#     "disk_size": "10G",
# }
# tags = {
#     "Name": "examplename",
#     "org": "Testorg",
#     "env": "sandbox",
#     "type": "Random type, maybe kubernetes?"
# }
#print(cloudinit_params)

#instance_data = vmHost.createInstance(user, instanceType, cloudinit_params, server_params, tags)
#print(instance_data["meta_data"]["vm_id"])

# img_data = GuestImage().getImageMeta("gmi-fc1c9a62")
# print(json.dumps(img_data, indent=4))

#img = UserImage(user)
#img.registerImage("/mnt/nvme/userimages/12345/user_vmi/vmi-4231ecb0.qcow2", "Unifi Controller", "Unifi controller on Ubuntu 16.04")

#GuestImage().registerImage("/data/ssd_storage/guest_images/windows_server_2012_r2_standard_eval_kvm_20170321.qcow2", "Windows Server 2020 R2 Standard Eval 64-bit", "Cloud image provided by cloudbase.it/windows-cloud-images/")

Instan