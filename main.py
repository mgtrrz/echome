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

user = {
    "account_id": "12345",
    "account_user_id": "11119",
}
#EchKeystore().store_key(user, "echome", "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC1Rkow4SIse59g2J16ykUBOYPRBMCShd9H/bwgFLRARESOsOiYazxVIBL++YPvDj2d+ZAmmiF+RbOBDsTqUO1FXaBQk2tz9WmkNU+22C+yNr54Mup63/yKKlGqJIUe/jH3VzmHFzBoBiSqBuR+ae9L1Wdy0Pj8vvP56vnbU1vuNQCmQMUAWlkjx346d/18O5IjSyc6VMeA3AXUlOHw061Mxq+qfwEx0X4Ndv13y6LBhSfySVXe8IDEnpad2PhlFTCzOkMn4/ZonPKrz52CScEuTID0WY+n964+3I2fL1Z/+iBnOzHWyLx44fhnDq0Gb8s7Mv8lUCRMLKcL9Cv6Kr4Ty38MEnsvtanTDU4W6tjz5G5ZxKXqC6XGOPjiUxmc4b1/+EPQASvd/0eBlQ/4g+Tlj6orcWq+ZK3Bgp4gVk+qFtOIlh9n0oeOiWkV5a9lhUdZzzmWh5VHYPWdU367UPcZEVHlpiEr6wNE7XA7D4rlvKvMY3r6a1LLXGWRHx2sfQk= mark@Marcuss-MacBook-Pro.local")

vmHost = vmManager()
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
    "image": "ubuntu-18.04-server-cloudimg-amd64.img",
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
#id = instance_data["meta_data"]["vm_id"]

vmHost.getInstanceMetaData(user, "vm-a411285c")




#vmHost.stop_vm("vm-04a800da")
#vmHost.terminateInstance(user, "vm-97bfcda8")

#vmHost.createVirtualMachineImage(user["account_id"], "vm-5946343e", "ubuntu-18.04-server-cloudimg-amd64.img")


gmi = GuestImage()
#results = gmi.getImageMeta("gmi-fc1c9a62")
results = gmi.getAllImages()
print(results)