import logging
import yaml
import json
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from echome.config import ecHomeConfig
from commander.cloudlocalds import CloudLocalds
from network.models import VirtualNetwork

logger = logging.getLogger(__name__)

KNOWN_CONTENT_TYPES = [
    'text/x-include-once-url',
    'text/x-include-url',
    'text/cloud-config-archive',
    'text/upstart-job',
    'text/cloud-config',
    'text/part-handler',
    'text/x-shellscript',
    'text/cloud-boothook',
]

NETWORK_CONFIG_FILE_NAME = "network.yaml"
USERDATA_CONFIG_FILE_NAME = "user-data"
METADATA_CONFIG_FILE_NAME = "meta-data"

class CloudInit:

    base_dir:str = None

    network_config:str = None
    userdata_config:str = None
    metadata:str = None

    def __init__(self, base_dir:str = None) -> None:
        self.base_dir = base_dir


    def generate_network_config(self, vnet: VirtualNetwork, priv_ip_addr=None):
        """Generate Cloudinit network config yaml

        Generates a network cloudinit config. This is meant to be used for BridgeToLan VMs
        where network information isn't set at VM build time but must instead be determined/
        set during boot with a Cloudinit script. VMs that use other network types should be
        able to set network configuration either through XML definition, virsh network
        interfaces, or possibly set through the metadata api.

        Args:
            vnet (VirtualNetwork): VirtualNetwork object where the virtual machine will be launched in. The vnet
                object will fill in details such as the gateway and DNS servers.
            priv_ip_addr (str, optional): Private IP address, defaults to None. If an IP address is not provided
                dhcp4 will be set to True. The Private IP address is not tested if it's valid for this
                network, please perform the check before calling this function. Defaults to None.

        Returns:
            str: CloudInit network contents in yaml format.
        """

        # Does a network config make sense for a NAT network?
        if vnet.type != VirtualNetwork.Type.BRIDGE_TO_LAN:
            # Other network types should use the metadata API
            logger.warn("Tried to create cloudinit network config for NAT network")
            return False

        if priv_ip_addr:
            private_ip = f"{priv_ip_addr}/{vnet.config['prefix']}"
            interface = {
                "dhcp4": False,
                "dhcp6": False,
                "addresses": [
                    private_ip
                ],
                "gateway4": vnet.config['gateway'],
                "nameservers": {
                    "addresses": vnet.config['dns_servers']
                }
            }
        else:
            interface = {
                "dhcp4": True,
                "dhcp6": False,
            }

        network_config = {
            "version": 2,
            "ethernets": {
                "ens2": interface
            }
        }

        contents = yaml.dump(network_config, default_flow_style=False, indent=2, sort_keys=False)
        self.network_config = contents
        self._write_file(NETWORK_CONFIG_FILE_NAME, contents)
        return contents
    

    def generate_userdata_config(self, vm_id: str, public_keys: list = None, user_data_script = None):
        """Generate Cloudinit Userdata config yaml

        Generates a basic cloudinit config with hostname and public key entries. The only
        required parameter is the virtual machine Id (VmId). Hostname and PublicKey can
        be left blank.

        Args:
            vm_id (str): Virtual Machine Id. Used to fill the hostname if Hostname is not provided.
            public_keys (list, optional): Public key to attach to the virtual machine. If not used, no SSH key will
            be provided. Defaults to None.
            user_data_script (str, optional): User-data shell script to boot the instance with. Defaults to None.

        Returns:
            str: The complete yaml config
        """

        # If hostname is not supplied, use the vm ID
        config_json = {
            "chpasswd": { "expire": False },
            "ssh_pwauth": False,
        }

        ssh_keys_json = {
            "ssh_authorized_keys": public_keys if public_keys is not None else []
        }

        # This is an incredibly hacky way to get json flow style output (retaining {expire: false} in the yaml output)
        # I'm unsure if cloudinit would actually just be happy receiving all YAML input.
        configfile = "#cloud-config\n"
        config_yaml = yaml.dump(config_json, default_flow_style=None, sort_keys=False)
        ssh_keys_yaml = yaml.dump(ssh_keys_json, default_flow_style=False, sort_keys=False, width=1000)

        yaml_config = configfile + config_yaml + ssh_keys_yaml

        if user_data_script:
            logger.debug("UserData script is included in request, making multipart file..")
            sub_messages = []
            format = 'x-shellscript'
            sub_message = MIMEText(user_data_script, format, sys.getdefaultencoding())
            sub_message.add_header('Content-Disposition', 'attachment; filename="shellscript.sh"')
            content_type = sub_message.get_content_type().lower()
            if content_type not in KNOWN_CONTENT_TYPES:
                logger.warning(f"WARNING: content type {content_type} may be incorrect!")
            sub_messages.append(sub_message)


            format = 'cloud-config'
            sub_message = MIMEText(yaml_config, format, sys.getdefaultencoding())
            sub_message.add_header('Content-Disposition', 'attachment; filename="userdata.yaml"')
            content_type = sub_message.get_content_type().lower()
            if content_type not in KNOWN_CONTENT_TYPES:
                logger.warning(f"WARNING: content type {content_type} may be incorrect!")
            sub_messages.append(sub_message)

            combined_message = MIMEMultipart()
            for msg in sub_messages:
                combined_message.attach(msg)
            logger.debug(combined_message)
            return str(combined_message)

        self.userdata_config = yaml_config
        self._write_file(USERDATA_CONFIG_FILE_NAME, yaml_config)
        return yaml_config
    

    def generate_metadata(self, vm_id, ip_addr=None, hostname=None, public_key:dict=None):
        echmd = ecHomeConfig.EcHomeMetadata()
        md = {
            "instance-id": vm_id,
            "local-hostname": hostname if hostname else self._gen_hostname(vm_id, ip_addr),
            "cloud-name": "ecHome",
            "availability-zone": echmd.availability_zone,
            "region": echmd.region,
            "public-keys": public_key if public_key else {}
        }

        contents = json.dumps(md, indent=4)
        self.metadata = contents
        self._write_file(METADATA_CONFIG_FILE_NAME, contents)
        return contents
    

    def create_iso(self, userdata_yaml_file_path:str = None, cloudinit_network_yaml_file_path:str = None,
            cloudinit_metadata_file_path:str = None) -> str:
        """Create the Cloudinit ISO to be mounted to the virtual machine.

        If no arguments are supplied, the function will use the files that were created from
        calling the other generate methods.

        Args:
            userdata_yaml_file_path (str, optional): Complete file path to the yaml cloudinit file. Defaults to None.
            cloudinit_network_yaml_file_path (str, optional): Complete file path to the network cloudinit file. Defaults to None.
            cloudinit_metadata_file_path (str, optional): Complete file path to the metadata cloudinit file. Defaults to None.

        Raises:
            CloudInitFailedValidation: If CloudInit could fails validation of the schema.
            CloudInitIsoCreationError: If CloudInit was not able to create the image.

        Returns:
            str: A complete file path to the location of the ISO file.
        """

        # Validate the yaml file
        logger.debug("Validating Cloudinit config yaml.")        
        if not CloudInit().validate_schema(userdata_yaml_file_path):
            logger.exception("Failed validating Cloudinit config yaml")
            raise CloudInitFailedValidation

        # Create cloud_init disk image
        cloudinit_iso_path = f"{self.base_dir}/cloudinit.iso"

        if userdata_yaml_file_path:
            userdata_file = userdata_yaml_file_path
        else:
            userdata_file = f"{self.base_dir}/{USERDATA_CONFIG_FILE_NAME}"
        
        if cloudinit_network_yaml_file_path:
            network_file = cloudinit_network_yaml_file_path
        elif self.network_config:
            network_file = f"{self.base_dir}/{NETWORK_CONFIG_FILE_NAME}"
        else:
            network_file = None
        
        if cloudinit_metadata_file_path:
            metadata_file = cloudinit_metadata_file_path
        elif self.metadata:
            metadata_file = f"{self.base_dir}/{METADATA_CONFIG_FILE_NAME}"
        else:
            metadata_file = None


        create_image_success = CloudLocalds().create_image(
            user_data_file=userdata_file,
            output=cloudinit_iso_path,
            meta_data_file=metadata_file,
            network_config_file=network_file
        )

        if not create_image_success:
            logger.exception("Was not able to create the cloud-init image!")
            raise CloudInitIsoCreationError

        logger.debug(f"Created cloudinit iso: {cloudinit_iso_path}")
        return cloudinit_iso_path
    
    def _write_file(self, file_name:str, contents:str):
        with open(file_name, "w") as filehandle:
            logger.debug(f"Writing contents to file: {file_name}")
            filehandle.write(contents)
        

class CloudInitFailedValidation(Exception):
    pass

class CloudInitIsoCreationError(Exception):
    pass
