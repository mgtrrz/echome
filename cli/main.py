import sys
import argparse
import logging
import json
from functools import reduce
import operator
from tabulate import tabulate
sys.path.insert(0, '../python_sdk/')
from echome import Session


APP_NAME="echome"

class ecHomeCli:
    def __init__(self):
        parser = argparse.ArgumentParser(
            description='ecHome CLI',
            usage='''echome <service> <subcommand> [<args>]

The most commonly used ecHome service commands are:
   vm         Interact with ecHome virtual machines.
   sshkeys    Interact with SSH keys used for virtual machines.
   images     Interact with guest and user images for virtual machines.
''')
        parser.add_argument('service', help='Service to interact with')
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.service):
            print('Unrecognized service')
            parser.print_help()
            exit(1)
        # use dispatch pattern to invoke method with same name
        getattr(self, args.service)()

    def vm(self):
        ecHomeCli_Vm()

    def sshkeys(self):
        ecHomeCli_SshKeys()
    
    def images(self):
        ecHomeCli_Images()

class ecHomeParent:

    # Parent service argument parser 
    # Landing pad for this service.
    def parent_service_argparse(self):

        parser = argparse.ArgumentParser(description=f"Interact with the {self.parent_full_name} service", prog=f"{APP_NAME} {self.parent_service}")

        parser.add_argument('subcommand', help=f"Subcommand for the {self.parent_service} service.", choices=self.get_list_of_methods())
        args = parser.parse_args(sys.argv[2:3])
        subcommand = str(args.subcommand).replace("-", "_")
        if not hasattr(self, subcommand):
            print('Unrecognized subcommand')
            parser.print_help()
            exit(1)

        # use dispatch pattern to invoke method with same name
        getattr(self, subcommand)()

    # Gets the list of public methods for the class. 
    # Converts underscores to dashes to automatically add into the ArgumentParser's choices variable
    def get_list_of_methods(self, exclude=[]):
        method_list = [func for func in dir(self) if callable(getattr(self, func))]
        exclude.append("get_list_of_methods")
        exclude.append("parent_service_argparse")

        methods = []
        for method in method_list:
            if not method.startswith("_") and not method in exclude:
                methods.append(method.replace("_", "-"))

        return methods
    
    @staticmethod
    # Traverse a dictionary to get a nested value from a list 
    def get_from_dict(dict, mapList):
        return reduce(operator.getitem, mapList, dict)

    # Generic function for printing a Tabulate table. Classes that inherit from this base class
    # should set __init__ variables: self.table_headers, self.data_columns with information for 
    # that resource. But they can be overwritten by setting parameters.
    # Nested dictionary items should be a list, e.g. '[dict_key1, ["dict_key2", "nested_key1"], dict_key3]'
    def print_table(self, objlist, header="", data_columns=""):
        if not header:
            header=self.table_headers
        
        if not data_columns:
            data_columns=self.data_columns
        
        all_rows = []
        for row in objlist:
            formatted_row = []

            for col in data_columns:
                if isinstance(col, list):
                    res = self.get_from_dict(row, col)
                    print(res)
                    print(type(res))
                else:
                    res = row[col]
                formatted_row.append(res)

            all_rows.append(formatted_row)

        print(tabulate(all_rows, header))



class ecHomeCli_Vm(ecHomeParent):

    def __init__(self):
        self.parent_service = "vm"
        self.parent_full_name = "Virtual Machine"
        
        self.session = Session()
        self.client = self.session.client("Vm")

        self.parent_service_argparse()
    
    def describe_all(self):
        parser = argparse.ArgumentParser(description='Describe all virtual machines', prog=f"{APP_NAME} {self.parent_service} describe-all")
        parser.add_argument('--format', '-f', help='Output format as JSON or Table', choices=["table", "json"], default=self.session.format)
        args = parser.parse_args(sys.argv[3:])

        if args.format == "table":
            vms = self.client.describe_all()
            self.print_table(vms)
        elif args.format == "json":
            print(json.dumps(self.client.describe_all(), indent=4))

    
    def describe(self):
        parser = argparse.ArgumentParser(description='Describe a virtual machine', prog=f"{APP_NAME} {self.parent_service} describe")
        parser.add_argument('vm_id',  help='Virtual Machine Id', metavar="<vm-id>")
        parser.add_argument('--format', '-f', help='Output format as JSON or Table', choices=["table", "json"], default=self.session.format)
        args = parser.parse_args(sys.argv[3:])

        if args.format == "table":
            vm = self.client.describe(args.vm_id)
            self.print_table(vm)
        elif args.format == "json":
            print(json.dumps(self.client.describe(args.vm_id), indent=4))

    
    def create(self):
        parser = argparse.ArgumentParser(description='Create a virtual machine', prog=f"{APP_NAME} {self.parent_service} create")

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
    
    def start(self):
        parser = argparse.ArgumentParser(description='Start a virtual machine', prog=f"{APP_NAME} {self.parent_service} start")
        parser.add_argument('vm_id',  help='Virtual Machine Id', metavar="<vm-id>")
        args = parser.parse_args(sys.argv[3:])

        print(self.client.start(args.vm_id))
    
    def stop(self):
        parser = argparse.ArgumentParser(description='Stop a virtual machine', prog=f"{APP_NAME} {self.parent_service} stop")
        parser.add_argument('vm_id',  help='Virtual Machine Id', metavar="<vm-id>")
        args = parser.parse_args(sys.argv[3:])

        print(self.client.stop(args.vm_id))
    
    def terminate(self):
        parser = argparse.ArgumentParser(description='Terminate a virtual machine', prog=f"{APP_NAME} {self.parent_service} terminate")
        parser.add_argument('vm_id',  help='Virtual Machine Id', metavar="<vm-id>")
        args = parser.parse_args(sys.argv[3:])

        print(self.client.terminate(args.vm_id))

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


class ecHomeCli_SshKeys(ecHomeParent):

    def __init__(self):
        self.parent_service = "sshkeys"
        self.parent_full_name = "SSH Keys"

        self.table_headers = ["Name", "Key Id", "Fingerprint"]
        self.data_columns = ["key_name", "key_id", "fingerprint"]

        self.session = Session()
        self.client = self.session.client("SshKey")

        self.parent_service_argparse()
    
    def describe_all(self):
        parser = argparse.ArgumentParser(description='Describe all SSH Keys', prog=f"{APP_NAME} {self.parent_service} describe-all")
        parser.add_argument('--format', '-f', help='Output format as JSON or Table', choices=["table", "json"], default=self.session.format)
        args = parser.parse_args(sys.argv[3:])
        
        if args.format == "table":
            keys = self.client.describe_all()
            self.print_table(keys)
        elif args.format == "json":
            print(json.dumps(self.client.describe_all(), indent=4))
    
    def describe(self):
        parser = argparse.ArgumentParser(description='Describe an SSH Key', prog=f"{APP_NAME} {self.parent_service} describe")
        parser.add_argument('key_name',  help='SSH Key Name', metavar="<key-name>")
        parser.add_argument('--format', '-f', help='Output format as JSON or Table', choices=["table", "json"], default=self.session.format)
        args = parser.parse_args(sys.argv[3:])
        
        if args.format == "table":
            key = self.client.describe(args.key_name)
            self.print_table(key)
        elif args.format == "json":
            print(json.dumps(self.client.describe(args.key_name), indent=4))
    
    def create(self):
        parser = argparse.ArgumentParser(description='Create an SSH Key', prog=f"{APP_NAME} {self.parent_service} create")
        parser.add_argument('key_name',  help='SSH Key Name', metavar="<key-name>")

        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--file',  help='Where a new file will be created with the contents of the private key', metavar="<./key-name.pem>")
        group.add_argument('--no-file',  help='Output only the PEM key in JSON to stdout instead of a file.', action='store_true')

        args = parser.parse_args(sys.argv[3:])

        response = self.client.create(args.key_name)
        if "error" in response:
           print(response)
           exit(1)

        if args.no_file:
            print(json.dumps(response, indent=4))
            exit(0)
        else:
            try:
                with open(args.file, "a") as file_object:
                    # Append 'hello' at the end of file
                    file_object.write(response["PrivateKey"])
                    response["PrivateKey"] = args.file
            except Exception as error:
                print(error)
                exit(1)

        print(json.dumps(response, indent=4))

    def delete(self):
        parser = argparse.ArgumentParser(description='Delete an SSH Key', prog=f"{APP_NAME} {self.parent_service} delete")
        parser.add_argument('key_name',  help='SSH Key Name', metavar="<key-name>")
        args = parser.parse_args(sys.argv[3:])

        print(json.dumps(self.client.delete(args.key_name), indent=4))
    

class ecHomeCli_Images(ecHomeParent):

    def __init__(self):
        self.parent_service = "images"
        self.parent_full_name = "Images"

        self.table_headers = ["Name", "Image Id", "Format", "Description"]
        self.data_columns=["name", "guest_image_id", ["guest_image_metadata", "format"], "description"]

        self.session = Session()
        self.client = self.session.client("Images")

        self.parent_service_argparse()

    def register(self):
        parser = argparse.ArgumentParser(description='Register an image', prog=f"{APP_NAME} {self.parent_service} register")
        parser.add_argument('--type',  help='Type of image to register', choices=["guest", "user"], required=True)
        parser.add_argument('--image-path',  help='Path to the new image. This image must exist on the new server and exist in the configured guest images directory.', metavar="</path/to/image>", dest="ImagePath", required=True)
        parser.add_argument('--image-name',  help='Name of the new image', metavar="<image-name>", required=True)
        parser.add_argument('--image-description',  help='Description of the new image', metavar="<image-desc>", required=True)
        args = parser.parse_args(sys.argv[3:])

        if args.type == "guest":
            resp = self.client.guest().register(
                ImagePath=args.ImagePath,
                ImageName=args.ImageName,
                ImageDescription=args.ImageDescription
            )
            print(json.dumps(resp))
        elif args.type == "user":
            print("got type user")
        else:
            logging.error("Unsupported Image type")
            exit(1)
    
    def describe(self):
        parser = argparse.ArgumentParser(description='Describe an image', prog=f"{APP_NAME} {self.parent_service} describe")
        parser.add_argument('image_id',  help='Image Id', metavar="<image-id>")
        parser.add_argument('--type',  help='Type of image to register', choices=["guest", "user"], required=True)
        parser.add_argument('--format', '-f', help='Output format as JSON or Table', choices=["table", "json"], default=self.session.format)
        args = parser.parse_args(sys.argv[3:])

        if args.type == "guest":

            image = self.client.guest().describe(args.image_id)

            if args.format == "table":
                self.print_table(image)
            elif args.format == "json":
                print(json.dumps(image, indent=4))

        elif args.type == "user":
            print("got type user")
        else:
            logging.error("Unsupported Image type")
            exit(1)
    
    def describe_all(self):
        parser = argparse.ArgumentParser(description='Describe all images', prog=f"{APP_NAME} {self.parent_service} describe-all")
        parser.add_argument('--type',  help='Type of image to register', choices=["guest", "user"], required=True)
        parser.add_argument('--format', '-f', help='Output format as JSON or Table', choices=["table", "json"], default=self.session.format)
        args = parser.parse_args(sys.argv[3:])

        if args.type == "guest":

            images = self.client.guest().describe_all()

            if args.format == "table":
                self.print_table(images)
            elif args.format == "json":
                print(json.dumps(images, indent=4))

        elif args.type == "user":
            print("got type user")
        else:
            logging.error("Unsupported Image type")
            exit(1)




if __name__ == "__main__":
    ecHomeCli()