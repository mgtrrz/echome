import logging
import os.path as path
from configparser import ConfigParser

CONFIG_FILE="/etc/echome/echome.ini"

class AppConfig:
    
    def __init__(self):
        self.check_config_file(CONFIG_FILE)
        self.parser = self.get_parser(CONFIG_FILE)

        sections = self.parser.sections()
        for section in sections:
            setattr(self, section, self.parser[section])

    def get_parser(self, config=CONFIG_FILE):
        parser = ConfigParser()
        parser.read(config)
        return parser
    
    def get_app_base_dir(self):
        return self.parser["echome"]["base_dir"]

    def check_config_file(self, file):
        if not path.exists(file):
            logging.error("ecHome config file at {file} not found or readable.")
            raise EcHomeConfigNotSet(f"ecHome config file at {file} not found or readable!")

        if(len(file) <= 0):
            logging.error("ecHome config file at {file} empty.")
            raise EcHomeConfigNotSet(f"ecHome config file at {file} empty!")



class EcHomeConfigNotSet(Exception):
    pass