from echome import Session, Vm, Images, SshKey
import logging

logging.basicConfig(level=logging.DEBUG)


#session = echome.Session()

vm_client = Session().client("Vm")

vms = vm_client.describe_all()
for vm in vms:
    name = vm["tags"]["Name"] if "Name" in vm["tags"] else ""
    print(f"{vm['instance_id']}\t{name}")


#thing = vm.describe_all()
# our_vm = vm.describe("vm-e7468d6e")
# print(our_vm.tags)


# ret = vm_client.create(
#     ImageId="gmi-fc1c9a62", 
#     InstanceSize="standard.medium",
#     NetworkInterfacePrivateIp="172.16.9.20/24",
#     NetworkInterfaceGatewayIp="172.16.9.1",
#     KeyName="echome",
#     DiskSize="50G",
#     Tags={"Name": "kubernetes_master", "Env": "staging", "Created_by": "mgutierrez"})

# ret = vm_client.create(
#     ImageId="gmi-fc1c9a62", 
#     InstanceSize="standard.medium",
#     NetworkInterfacePrivateIp="172.16.9.21/24",
#     NetworkInterfaceGatewayIp="172.16.9.1",
#     KeyName="echome",
#     DiskSize="50G",
#     Tags={"Name": "kubernetes_worker_1", "Env": "staging", "Created_by": "mgutierrez"})

# ret = vm_client.create(
#     ImageId="gmi-fc1c9a62", 
#     InstanceSize="standard.medium",
#     NetworkInterfacePrivateIp="172.16.9.22/24",
#     NetworkInterfaceGatewayIp="172.16.9.1",
#     KeyName="echome",
#     DiskSize="50G",
#     Tags={"Name": "kubernetes_worker_2", "Env": "staging", "Created_by": "mgutierrez"})

# print(ret)
#print(vm.status_code)

# images = Session().client("Images")
# ret = images.guest().describe_all()
# #print(ret)

# # SshKeys
# sshkey = Session().client("SshKey")

# ret = sshkey.describe("echome")
#print(ret.fingerprint)