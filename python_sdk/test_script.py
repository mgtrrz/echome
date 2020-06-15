from echome import Session, Vm, Images, SshKey
import logging
import json

logging.basicConfig(level=logging.DEBUG)


session = Session()
vm_client = session.client("Vm")

vms = vm_client.describe_all()
print("VMs__________________________________")
for vm in vms:
    name = vm["tags"]["Name"] if "Name" in vm["tags"] else ""
    print(f"{vm['instance_id']}\t{name}")


#thing = vm.describe_all()
# our_vm = vm.describe("vm-e7468d6e")
# print(our_vm.tags)


# ret = vm_client.create(
#     ImageId="gmi-fc1c9a62", 
#     InstanceSize="standard.micro",
#     NetworkType="BridgeToLan",
#     NetworkInterfacePrivateIp="172.16.9.26/24",
#     NetworkInterfaceGatewayIp="172.16.9.1",
#     KeyName="echome",
#     DiskSize="10G",
#     Tags={"Name": "test_instance", "Env": "staging", "Created_by": "mgutierrez"})

# ret = vm_client.create(
#     ImageId="gmi-fc1c9a62", 
#     InstanceSize="standard.medium",
#     NetworkType="BridgeToLan",
#     NetworkInterfacePrivateIp="172.16.9.21/24",
#     NetworkInterfaceGatewayIp="172.16.9.1",
#     KeyName="echome",
#     DiskSize="50G",
#     Tags={"Name": "kubernetes_worker_1", "Env": "staging", "Created_by": "mgutierrez"})

# ret = vm_client.create(
#     ImageId="gmi-fc1c9a62", 
#     InstanceSize="standard.medium",
#     NetworkType="BridgeToLan",
#     NetworkInterfacePrivateIp="172.16.9.22/24",
#     NetworkInterfaceGatewayIp="172.16.9.1",
#     KeyName="echome",
#     DiskSize="50G",
#     Tags={"Name": "kubernetes_worker_2", "Env": "staging", "Created_by": "mgutierrez"})

# print(ret)
#print(vm.status_code)


# resp = Session().client("Images").guest().register(
#     ImagePath="/mnt/nvme/guestimages/CentOS-7-x86_64-GenericCloud-2003.qcow2",
#     ImageName="CentOS 7",
#     ImageDescription="CentOS 7 Cloud image"
# )
# print(resp)

# guest_images = Session().client("Images").guest().describe_all()

# print("\nGuest Images_______________________")
# for guest_img in guest_images:
#     print(f"{guest_img['guest_image_id']}\t{guest_img['name']}")




# ssh_keys = Session().client("SshKey").describe_all()
# print("\nSSH Keys___________________________")
# for sshkey in ssh_keys:
#     print(f"{sshkey['key_id']}\t{sshkey['key_name']}\t{sshkey['fingerprint']}")


# # SshKeys
# sshkey = Session().client("SshKey")

# ret = sshkey.describe("echome")
#print(ret.fingerprint)