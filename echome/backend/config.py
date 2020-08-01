import logging
import os.path as path
from configparser import ConfigParser

CONFIG_FILE="/etc/echome/echome.ini"

class AppConfig:
    
    def __init__(self):
        self.check_config_file(CONFIG_FILE)

    def get_parser(self, config=CONFIG_FILE):
        parser = ConfigParser()
        parser.read(config)
        return parser

    def check_config_file(self, file):
        if not path.exists(file):
            logging.error("ecHome config file at {file} not found or readable.")
            raise EcHomeConfigNotSet(f"ecHome config file at {file} not found or readable!")

        if(len(file) <= 0):
            logging.error("ecHome config file at {file} empty.")
            raise EcHomeConfigNotSet(f"ecHome config file at {file} empty!")
    
    class __base_section():
        ini_section = __name__
        def __init__(self):
            parser = AppConfig().get_parser()
            for key in parser[self.ini_section]:
                setattr(self, key, parser[self.ini_section][key])

    class EcHomeMetadata(__base_section):
        ini_section = "Metadata"

        # Defaults
        region = "Earth"
        availability_zone = "Home"
    
    class VirtualMachines(__base_section):
        ini_section = "VirtualMachines"

        guest_images_dir = None
        user_dir = None
    
    class EcHome(__base_section):
        ini_section = "echome"

        base_dir = "/opt/echome/app/backend"
        api_secret = None
        api_server_log = "/var/log/echome/api_server.log"
        
        api_url = None
        api_port = None
        metadata_api_url = None
        metadata_api_port = None
    
    class Database(__base_section):
        ini_section = "database"

        url = None
        

class EcHomeConfigNotSet(Exception):
    pass

ecHomeConfig = AppConfig()
