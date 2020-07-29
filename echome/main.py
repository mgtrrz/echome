import libvirt
import sys
import json
import logging
from backend.vm_manager import VmManager
from backend.ssh_keystore import KeyStore
from backend.instance_definitions import Instance
from backend.guest_image import GuestImage, UserImage
from backend.config import AppConfig
from backend.user import User
from backend.database import DbEngine


logging.basicConfig(level=logging.DEBUG)

# user account for testing
db = DbEngine()
dbsession = db.return_session()
user = dbsession.query(User).filter_by(user_id="user-d4193166").first()
print(user)


#vmHost.terminateInstance(user, "vm-1cde03da")
#vmHost.createVirtualMachineImage(user, "vm-ca065ed2")

# metadata = vmHost.getInstanceMetaData(user, "vm-b49c2840")
# print(metadata)

# Example Instance definition
# instanceType = Instance("standard", "small")


def create_vm():
    vmHost = VmManager()
    key_meta = KeyStore().get_key(user, "echome-server")

    instanceType = Instance("standard", "small")

    cloudinit_params = {
        "cloudinit_key_name": key_meta[0]["key_name"],
        "cloudinit_public_key": key_meta[0]["public_key"],
        "network_type": "None", # BridgeToLan, None
        "private_ip": "172.16.9.21/24",
        "gateway_ip": "172.16.9.1",
    }
    server_params = {
        "image_id": "gmi-d8cacd92",
        "disk_size": "10G",
    }
    tags = {
        "Name": "bridge-example",
        "org": "Testorg",
    }
    print(cloudinit_params)

    instance_data = vmHost.createVirtualMachine(user, instanceType, cloudinit_params, server_params, tags, custom_xml="create_vm_nat_network.xml")
    print(f"creating {instance_data}")


create_vm()


#print(instance_data["meta_data"]["vm_id"])

# img_data = GuestImage().getImageMeta("gmi-fc1c9a62")
# print(json.dumps(img_data, indent=4))

#img = UserImage(user)
#img.registerImage("/mnt/nvme/userimages/12345/user_vmi/vmi-4231ecb0.qcow2", "Unifi Controller", "Unifi controller on Ubuntu 16.04")

#GuestImage().registerImage("/data/ssd_storage/guest_images/windows_server_2012_r2_standard_eval_kvm_20170321.qcow2", "Windows Server 2020 R2 Standard Eval 64-bit", "Cloud image provided by cloudbase.it/windows-cloud-images/")