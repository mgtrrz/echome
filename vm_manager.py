import libvirt
from string import Template
import uuid
import pathlib
import logging
import subprocess
import random
import shutil
import time
import json
import datetime
from database import Database
from sqlalchemy import select, and_
from instance_definitions import Instance
from id_gen import IdGenerator
import guest_image

VM_ROOT_DIR = "/data/ssd_storage/user_instances"
VM_GUEST_IMGS = "/data/ssd_storage/guest_images"

CLEAN_UP_ON_FAIL = True

# Flow for VM Creation
# 1. Generate a VM Id
# 2. Generate the cloudinit config
#   a. Save the cloudinit config to a temporary folder
#   b. validate the file
#   c. create an disk img for the cloudinit file
# 3. Generate the VM XML document
# 4. Launch new VM with XML document

class vmManager:

    def __init__(self):
        self.currentConnection = libvirt.open('qemu:///system')
        self.db = Database()

    def getConnection(self):
        return self.currentConnection

    def closeConnection(self):
        self.currentConnection.close()

    def createInstance(self, user, instanceType:Instance, cloudinit_params, server_params, tags):

        logging.debug("Generating vm-id")
        vm_id = IdGenerator.generate()
        logging.debug(f"Generated vm-id: {vm_id}")

        # Generating the tmp path for creating/copying/validating files
        vmdir = self.__generate_vm_path(user["account_id"], vm_id)
        logging.debug(f"Create VM directory: {vmdir}")


        # Generate cloudinit config
        cloudinit_params["vm_id"] = vm_id
        standard_cloudinit_config = self.__generate_cloudinit_config(cloudinit_params)
        # Create the Cloudinit yaml in tmp dir
        cloudinit_yaml_file_path = f"{vmdir}/cloudinit.yaml"

        with open(cloudinit_yaml_file_path, "w") as filehandle:
            logging.debug("Writing cloudinit yaml: cloudinit.yaml")
            filehandle.write(standard_cloudinit_config)
        # TODO: Catch errors 

        # If we set a static IP for the instance, create a network config file
        network_yaml_file_path = ""
        network_config_at_launch = {}
        if "private_ip" in cloudinit_params:
            network_config_at_launch["private_ip"] = cloudinit_params["private_ip"]
            network_config_at_launch["gateway"] = cloudinit_params["gateway_ip"]
            network_cloudinit_config = self.__generate_network_cloudinit_config(cloudinit_params)
            network_yaml_file_path = f"{vmdir}/network.yaml"

            with open(network_yaml_file_path, "w") as filehandle:
                logging.debug("Writing cloudinit yaml: network.yaml")
                filehandle.write(network_cloudinit_config)
            # TODO: Catch errors 

        # Validate and create the cloudinit iso
        cloudinit_iso_path = self.__create_cloudinit_iso(vmdir, cloudinit_yaml_file_path, network_yaml_file_path)

        # Is this a guest image or a user-created virtual machine image?
        logging.debug("Determining image metadata..")
        gmi = guest_image.GuestImage()
        if "image_id" not in server_params:
            msg = f"Image Id was not found in launch configuration. Cannot continue!"
            logging.error(msg)
            if CLEAN_UP_ON_FAIL:
                self.__delete_vm_path(user["account_id"], vm_id)
            raise InvalidLaunchConfiguration(msg)

        try:
            logging.debug(f"Using 'image_id', grabbing image metadata from {server_params['image_id']}")
            img = gmi.getImageMeta(server_params['image_id'])
        except guest_image.InvalidImageId as e:
            logging.error(e)
            if CLEAN_UP_ON_FAIL:
                self.__delete_vm_path(user["account_id"], vm_id)
            raise guest_image.InvalidImageId(e)
            
        logging.debug(json.dumps(img, indent=4))
        img_type = "base guest image"
        img_path = img["guest_image_path"]
        img_format = img["guest_image_metadata"]["format"]
        #image_base_dir = f"{VM_GUEST_IMGS}"

        vm_image_metadata = {
            "image_id": server_params["image_id"],
            "image_name": img["name"],
        }

        logging.debug("Creating copy of VM Image")
        # Create a copy of the VM image
        vm_img = f"{vmdir}/{vm_id}.{img_format}"
        try:
            logging.debug(f"Copying {img_type}: {img_path} TO directory {vmdir} as {vm_id}.{img_format}")
            shutil.copy2(img_path, vm_img)
        except:
            logging.error("Encountered an error on VM copy. Cannot continue.")
            if CLEAN_UP_ON_FAIL:
                self.__delete_vm_path(user["account_id"], vm_id)
            raise

        logging.debug(f"Final image: {vm_img}")

        # Generate VM
        logging.debug(f"Generating vm config")
        vm_config = {
            "vm_id": vm_id,
            "cpu": instanceType.get_cpu(),
            "memory": instanceType.get_memory(),
            "xml_template": instanceType.get_xml_template(),
            "cloud_init_path": cloudinit_iso_path,
            "vm_img": vm_img
        }
        logging.debug(vm_config)
        xmldoc = self.__generate_new_vm_template(vm_config)

        # Create the actual files in the tmp dir
        with open(f"{vmdir}/vm.xml", 'w') as filehandle:
            logging.debug("Writing virtual machine doc: vm.xml")
            filehandle.write(xmldoc)

        logging.debug(xmldoc)
        logging.debug(standard_cloudinit_config)

        logging.debug(f"Resizing image size to {server_params['disk_size']}")
        output = self.__run_command(['qemu-img', 'resize', vm_img, server_params["disk_size"]])
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")

        
        logging.debug("Attempting to define XML with virsh..")
        self.currentConnection.defineXML(xmldoc)
        
        logging.debug("Setting autostart to 1")
        domain = self.__get_virtlib_domain(vm_id)
        domain.setAutostart(1)
        
        logging.info("Starting VM..")
        self.startInstance(vm_id)


        interfaces = {
            "config_at_launch": network_config_at_launch
        }

        # Add the information for this VM in the db
        stmt = self.db.user_instances.insert().values(
            account = user["account_id"],
            instance_id = vm_id,
            host = "localhost",
            instance_type = instanceType.itype,
            instance_size = instanceType.isize,
            account_user = user["account_user_id"],
            attached_interfaces = interfaces,
            attached_storage = {},
            key_name = cloudinit_params["cloudinit_key_name"],
            assoc_firewall_rules = {},
            vm_image_metadata = vm_image_metadata,
            tags = tags,
        )
        print(stmt)
        result = self.db.connection.execute(stmt)

        print(f"Successfully created VM: {vm_id} : {vmdir}")
        return vm_id
    
    # Get information about a instance/VM
    def getInstanceMetaData(self, user_obj, vm_id):

        select_stmt = select([self.db.user_instances]).where(
            and_(
                self.db.user_instances.c.account == user_obj["account_id"], 
                self.db.user_instances.c.instance_id == vm_id
            )
        )
        rows = self.db.connection.execute(select_stmt).fetchall()
        instances = []
        if rows:
            result = rows[0]
            data = {}
            i = 0
            for col in self.db.user_instances.columns:
                if col.name == "tags":
                    data[col.name] = result[i]
                else:
                    data[col.name] = str(result[i])
                i += 1
            # Get instance state
            state, state_int, _  = self.getVmState(vm_id)
            data["state"] = {
                "code": state_int,
                "state": state,
            }
            instances.append(data)

        return instances
    
    # Returns all instances belonging to the account/user
    def getAllInstances(self, user_obj):
        columns = [
            self.db.user_instances.c.created,
            self.db.user_instances.c.instance_id,
            self.db.user_instances.c.instance_type,
            self.db.user_instances.c.instance_size,
            self.db.user_instances.c.vm_image_metadata,
            self.db.user_instances.c.account_user,
            self.db.user_instances.c.attached_interfaces,
            self.db.user_instances.c.attached_storage,
            self.db.user_instances.c.key_name,
            self.db.user_instances.c.assoc_firewall_rules,
            self.db.user_instances.c.tags
        ]
        select_stmt = select(columns).where(self.db.user_instances.c.account == user_obj["account_id"])
        rows = self.db.connection.execute(select_stmt).fetchall()
        instances = []
        if rows:
            for row in rows:
                instance = {}
                i = 0
                for col in columns:
                    if col.name == "tags":
                        instance[col.name] = row[i]
                    else:
                        instance[col.name] = str(row[i])
                    i += 1

                state, state_int, _  = self.getVmState(instance["instance_id"])
                instance["state"] = {
                    "code": state_int,
                    "state": state,
                }
                instances.append(instance)
        return instances

    def createVirtualMachineImage(self, user, account_id, vm_id, vm_name):
        logging.debug(f"Creating VMI from {vm_name}")
        # Instance needs to be turned off to create an image
        self.stopInstance(vm_id)

        vmi_id = IdGenerator.generate("vmi")

        user_vmi_dir = f"{VM_ROOT_DIR}/{account_id}/user_vmi"
        # Create it if doesn't exist
        pathlib.Path(user_vmi_dir).mkdir(parents=True, exist_ok=True)

        new_image_full_path = f"{user_vmi_dir}/{vmi_id}.qcow2"

        try:
            logging.debug(f"Copying image: {vm_name} TO {vmi_id}")
            shutil.copy2(f"{VM_ROOT_DIR}/{account_id}/{vm_id}/{vm_name}", new_image_full_path)
        except:
            logging.error("Encountered an error on VM copy. Cannot continue.")
            raise
        
        logging.debug(f"Running Sysprep on: {new_image_full_path}")
        output = self.__run_command(["sudo", "virt-sysprep", "-a", new_image_full_path])
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")

        logging.debug(f"Running Sparsify on: {new_image_full_path}")
        self.__run_command(["sudo", "virt-sparsify", "--compress", new_image_full_path])
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")
        
        return {
            "success": True,
            "meta_data": {
                "vmi_id": vmi_id,
                "vmi_id_file_name": f"{vmi_id}.qcow2",
            },
            "reason": "",
        }

    def getVmState(self, vm_id):
        domain = self.__get_virtlib_domain(vm_id)
        state_int, reason = domain.state()

        if state_int == libvirt.VIR_DOMAIN_NOSTATE:
            state_str = "no_state"
        elif state_int == libvirt.VIR_DOMAIN_RUNNING:
            state_str = "running"
        elif state_int == libvirt.VIR_DOMAIN_BLOCKED:
            state_str = "blocked"
        elif state_int == libvirt.VIR_DOMAIN_PAUSED:
            state_str = "paused"
        elif state_int == libvirt.VIR_DOMAIN_SHUTDOWN:
            state_str = "shutdown"
        elif state_int == libvirt.VIR_DOMAIN_SHUTOFF:
            state_str = "shutoff"
        elif state_int == libvirt.VIR_DOMAIN_CRASHED:
            state_str = "crashed"
        elif state_int == libvirt.VIR_DOMAIN_PMSUSPENDED:
            # power management (entered into s3 state)
            state_str = "pm_suspended"
        else:
            state_str = "unknown"

        return state_str, state_int, str(reason)

            

    def startInstance(self, vm_id):
        vm = self.__get_virtlib_domain(vm_id)
        if not vm:
            return {
                "success": False,
                "meta_data": {},
                "reason": f"VM {vm_id} does not exist",
            }

        if vm.isActive():
            logging.info(f"VM '{vm_id}' already started")

        while not vm.isActive():
            logging.info(f"Starting VM '{vm_id}'")
            vm.create()
        
        return {
            "success": True,
            "meta_data": {},
            "reason": "",
        }
    
    def stopInstance(self, vm_id):
        logging.debug(f"Stopping vm: {vm_id}")
        vm = self.__get_virtlib_domain(vm_id)
        if not vm:
            return {
                "success": False,
                "meta_data": {},
                "reason": f"VM {vm_id} does not exist",
            }

        if not vm.isActive():
            logging.info(f"VM '{vm_id}' already stopped")
            return 

        if vm.isActive():
            print(f"Stopping VM '{vm_id}'")
        else:
            print(f"VM '{vm_id}' is already stopped")

        vm_force_stop_time = 240
        seconds_waited = 0
        while vm.isActive():
            try:
                vm.shutdown()
                time.sleep(1)
                seconds_waited += 1
                if seconds_waited >= vm_force_stop_time:
                    logging.warning(f"Timeout was reached and VM '{vm_id}' hasn't stopped yet. Force shutting down...")
                    vm.destroy()
            except libvirt.libvirtError as e:
                # Error code 55 = Not valid operation: domain is not running
                if (e.get_error_code() == 55):
                    pass
                else:
                    raise(e)

        return {
            "success": True,
            "meta_data": {},
            "reason": "",
        }

    # Terminate the instance 
    def terminateInstance(self, user_obj, vm_id):
        logging.debug(f"Terminating vm: {vm_id}")
        account_id = user_obj["account_id"]

        vm = self.__get_virtlib_domain(vm_id)
        if not vm:
            return {
                "success": False,
                "meta_data": {},
                "reason": f"VM {vm_id} does not exist",
            }
        try:
            # Stop the instance
            self.stopInstance(vm_id)
            # Undefine it to remove it from virt
            vm.undefine()
        except libvirt.libvirtError as e:
            logging.error(f"Could not terminate instance {vm_id}: libvirtError {e}")
            return {
                "success": False,
                "meta_data": {},
                "reason": f"Could not terminate instance {vm_id}: libvirtError {e}",
            }
        
        # Delete folder/path
        self.__delete_vm_path(account_id, vm_id)

        # delete entry in db
        del_stmt = self.db.user_instances.delete().where(self.db.user_instances.c.instance_id == vm_id)
        self.db.connection.execute(del_stmt)

        return {
            "success": True,
            "meta_data": {},
            "reason": "",
        }

    # Returns currentConnection object if the VM exists. Returns False if vm does not exist.
    def __get_virtlib_domain(self, vm_id):
        try:
            return self.currentConnection.lookupByName(vm_id)
        except libvirt.libvirtError as e:
            # Error code 42 = Domain not found
            if (e.get_error_code() == 42):
                return False

    # Generate XML template for virt to create the image with
    def __generate_new_vm_template(self, config):
        cloudinit_xml = ""
        
        # Generate disk XML
        if config["cloud_init_path"]:
            with open(f"./xml_templates/cloudinit_disk.xml", 'r') as filehandle:
                cloudinit_xml = Template(filehandle.read())
                replace = {
                    'VM_USER_CLOUDINIT_IMG_PATH': config["cloud_init_path"]
                }
                cloudinit_xml = cloudinit_xml.substitute(replace)

        # Generate the rest of the vm XML
        with open(f"./xml_templates/{config['xml_template']}", 'r') as filehandle:
            src = Template(filehandle.read())
            replace = {
                'VM_NAME': config["vm_id"],
                'VM_CPU_COUNT': config["cpu"], 
                'VM_MEMORY': config["memory"],
                'CLOUDINIT_DISK': cloudinit_xml,
                'VM_USER_IMG_PATH': config["vm_img"]
            }
        
        return src.substitute(replace)
    
    # Generate cloudinit yaml string
    def __generate_cloudinit_config(self, config):
        # If hostname is not supplied, use the instance ID
        if "hostname" not in config or config["hostname"] == "":
            config["hostname"] = config["vm_id"]

        cloud_init = """#cloud-config
chpasswd: {{ expire: False }}
ssh_pwauth: False
hostname: {}
ssh_authorized_keys:
  - {}
        """.format(config["hostname"], config["cloudinit_public_key"])
        return cloud_init


    # Generate network config for cloudinit yaml string
    def __generate_network_cloudinit_config(self, config):
        cloud_network_init = f"""version: 2
ethernets:
    ens2:
        dhcp4: false
        dhcp6: false
        addresses:
          - {config['private_ip']}
        gateway4: {config['gateway_ip']}
        nameservers:
          addresses:
            - 1.1.1.1
            - 1.0.0.1
        """

        return cloud_network_init
    
    # Generate an ISO from the cloudinit YAML files
    def __create_cloudinit_iso(self, vmdir, cloudinit_yaml_file_path, cloudinit_network_yaml_file_path=""):

        # Validate the yaml file
        logging.debug("Validating Cloudinit config yaml.")        
        output = self.__run_command(['cloud-init', 'devel', 'schema', '--config-file', cloudinit_yaml_file_path])
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")

        if cloudinit_network_yaml_file_path:
            logging.debug("Validating Cloudinit Network config yaml.")
            output = self.__run_command(['cloud-init', 'devel', 'schema', '--config-file', cloudinit_network_yaml_file_path])
            if output["return_code"] is not None:
                # There was an issue with the resize
                #TODO: Condition on error
                print("Return code not None")


        # Create cloud_init disk image
        cloudinit_iso_path = f"{vmdir}/cloudinit.iso"

        args = ['cloud-localds', '-v', cloudinit_iso_path, cloudinit_yaml_file_path]

        if cloudinit_network_yaml_file_path:
            args.append(f"--network-config={cloudinit_network_yaml_file_path}")

        output = self.__run_command(args)
        if output["return_code"] is not None:
            # There was an issue with the resize
            #TODO: Condition on error
            print("Return code not None")

        logging.debug(f"Created cloudinit iso: {cloudinit_iso_path}")

        return cloudinit_iso_path

    def __generate_mac_addr(self):
        mac = [ 0x00, 0x16, 0x3e,
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0xff),
            random.randint(0x00, 0xff) ]
        return ':'.join(map(lambda x: "%02x" % x, mac))

    # Create a path for the files to be created in
    def __generate_vm_path(self, account_id, vm_id):
        vm_path = f"{VM_ROOT_DIR}/{account_id}/{vm_id}"
        try:
            pathlib.Path(vm_path).mkdir(parents=True, exist_ok=False)
            return vm_path
        except:
            logging.error("Encountered an error when attempting to generate VM path. Cannot continue.")
            raise

    # Delete the path for the files
    def __delete_vm_path(self, account_id, vm_id):
        path = f"{VM_ROOT_DIR}/{account_id}/{vm_id}"
        logging.debug(f"Deleting VM Path: {path}")

        try:
            shutil.rmtree(path)
        except:
            logging.error("Encountered an error when atempting to delete VM path.")

    def __run_command(self, cmd: list):
        logging.debug("Running command: ")
        logging.debug(cmd)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
        output = process.stdout.readline()
        logging.debug(output.strip())
        return_code = process.poll()
        logging.debug(f"SUBPROCESS RETURN CODE: {return_code}")
        return {
            "return_code": return_code,
            "output": output,
        }

class InvalidLaunchConfiguration(Exception):
    pass