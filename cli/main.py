import sys
import argparse
import logging
import json
from tabulate import tabulate
sys.path.insert(0, '../python_sdk/')
from echome import Session


class ecHomeCli:
    def __init__(self):
        parser = argparse.ArgumentParser(
            description='ecHome CLI',
            usage='''echome <service> <subcommand> [<args>]

The most commonly used ecHome commands are:
   vm         Interact with ecHome virtual machines.
   fetch      Download objects and refs from another repository
''')
        parser.add_argument('command', help='Service to interact with')
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print('Unrecognized command')
            parser.print_help()
            exit(1)
        # use dispatch pattern to invoke method with same name
        getattr(self, args.command)()

    def vm(self):
        ecHomeCli_Vm()


    def fetch(self):
        parser = argparse.ArgumentParser(
            description='Download objects and refs from another repository')
        # NOT prefixing the argument with -- means it's not optional
        parser.add_argument('repository')
        args = parser.parse_args(sys.argv[2:])
        print(f"Running git fetch, repository={args.repository}")

class ecHomeCli_Vm:

    def __init__(self):
        parser = argparse.ArgumentParser(description='Interact with the Virtual Machine service')

        parser.add_argument('subcommand', help='Subcommand for the vm service.')
        args = parser.parse_args(sys.argv[2:3])
        subcommand = str(args.subcommand).replace("-", "_")
        if not hasattr(self, subcommand):
            print('Unrecognized subcommand')
            parser.print_help()
            exit(1)
        
        self.client = Session().client("Vm")
        # use dispatch pattern to invoke method with same name
        getattr(self, subcommand)()
    
    def describe_all(self):
        parser = argparse.ArgumentParser(description='Describe all virtual machines', prog="echome vm describe-all")
        parser.add_argument('--format', '-f', help='Output format as JSON or Table', choices=["table", "json"])
        args = parser.parse_args(sys.argv[3:])

        if args.format == "table":
            vms = self.client.describe_all()
            self.print_table(vms)
        elif args.format == "json":
            print(json.dumps(self.client.describe_all(), indent=4))

    
    def describe(self):
        parser = argparse.ArgumentParser(description='Describe a virtual machine', prog="echome vm describe")
        parser.add_argument('vm_id',  help='Virtual Machine Id', metavar="<vm-id>")
        parser.add_argument('--format', '-f', help='Output format as JSON or Table', choices=["table", "json"])
        args = parser.parse_args(sys.argv[3:])

        if args.format == "table":
            vm = self.client.describe(args.vm_id)
            self.print_table(vm)
        elif args.format == "json":
            print(json.dumps(self.client.describe(args.vm_id), indent=4))

    
    def create(self):
        parser = argparse.ArgumentParser(description='Create a virtual machine', prog="echome vm create")

        parser.add_argument('--image-id', help='Image Id', required=True, metavar="<value>", dest="ImageId")
        parser.add_argument('--instance-size', help='Instance Size', required=True, metavar="<value>", dest="InstanceSize")
        parser.add_argument('--network-type', help='Network type', metavar="<value>", dest="NetworkType")
        parser.add_argument('--private-ip', help='Network private IP', metavar="<value>", dest="NetworkInterfacePrivateIp")
        parser.add_argument('--gateway-ip', help='Network gateway IP', metavar="<value>", dest="NetworkInterfaceGatewayIp")
        parser.add_argument('--key-name', help='Key name', metavar="<value>", dest="KeyName")
        parser.add_argument('--disk-size', help='Disk size', metavar="<value>", dest="DiskSize")
        parser.add_argument('--tags', help='Tags', type=json.loads, metavar='{"Key": "Value", "Key": "Value"}', dest="Tags")
        args = parser.parse_args(sys.argv[3:])

        # ** unpacks the arguments, vars() returns the variables and provides them to client.create() as
        # ImageId=gmi-12345, InstanceSize=standard.small, etc.
        print(self.client.create(**vars(args)))
    
    def stop(self):
        pass

    def print_table(self, vm_list):
        headers = ["Name", "Vm Id", "Instance Size", "State", "IP", "Image", "Created"]
        all_vms = []
        for vm in vm_list:
            name = vm["tags"]["Name"] if "Name" in vm["tags"] else ""
            isize = f"{vm['instance_type']}.{vm['instance_size']}"
            if vm["attached_interfaces"]:
                ip = vm["attached_interfaces"]["config_at_launch"]["private_ip"]
            else:
                ip = ""

            if vm['vm_image_metadata']:
                image = "{} ({})".format(vm['vm_image_metadata']['image_id'], vm['vm_image_metadata']['image_name'])
            else:
                image = ""

            v = [name, vm["instance_id"], isize, vm["state"]["state"], ip, image, vm["created"]]
            all_vms.append(v)

        print(tabulate(all_vms, headers))

if __name__ == "__main__":
    ecHomeCli()