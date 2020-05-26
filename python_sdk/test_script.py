from echome import Session
import logging

logging.basicConfig(level=logging.DEBUG)


#session = echome.Session()

vm = Session().resource("Vm")

#thing = vm.describe_all_vms()
#thing = vm.describe_vm("vm-e7468d6e")

# ret = vm.create(
#     ImageId="gmi-fc1c9a62", 
#     InstanceSize="standard.small",
#     NetworkInterfacePrivateIp="172.16.9.19/24",
#     NetworkInterfaceGatewayIp="172.16.9.1",
#     KeyName="echome",
#     DiskSize="20G",
#     Tags={"Name": "ApiTest", "Env": "production", "Created_by": "mgutierrez"})
# print(ret)
#print(vm.status_code)

ret = Session().resource("Images").guest().describe_all()
print(ret)