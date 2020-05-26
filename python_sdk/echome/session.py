import logging
from configparser import ConfigParser
from os import getenv
from pathlib import Path
import sys
from .vm import Vm, Images

default_echome_dir = ".echome"
default_config_file = "config"
default_credential_file = "credentials"
default_profile = "default"
default_connection = "insecure"
api_version = "v1"

# Grabs the config and credentials from the user's home dir
# and establishes a connection with the server and authorization
class Session:

    def __init__(self):
        home_dir = str(Path.home())
        echome_dir = f"{home_dir}/{default_echome_dir}"

        cred_file  = f"{echome_dir}/{default_credential_file}"
        conf_file  = f"{echome_dir}/{default_config_file}"

        self.current_profile = getenv("ECHOME_PROFILE", default_profile)

        try:
            config_from_file = self.__get_local_config(conf_file, self.current_profile)
        except ConfigFileError as e:
            raise ConfigFileError(e)

        try:
            creds_from_file = self.__get_local_credentials(cred_file, self.current_profile)
        except CredentialsFileError as e:
            raise CredentialsFileError(e)
        
        self.server_url = getenv("ECHOME_SERVER", config_from_file["server"])
        self.access_id  = getenv("ECHOME_ACCESS_ID", creds_from_file["access_id"])
        self.secret_key = getenv("ECHOME_SECRET_KEY", creds_from_file["secret_key"])
        self.connection_type = getenv("ECHOME_PROTOCOL", config_from_file["protocol"] if "protocol" in config_from_file else default_connection)
        if self.connection_type == "insecure":
            self.protocol = "http://"
        elif self.connection_type == "secure":
            self.protocol = "https://"
        else:
            raise ConfigFileError(f"Unknown connection type specified. Use either 'secure' or 'insecure'. A blank value defaults to {default_connection}")

        self.api_version = api_version

    def __get_local_config(self, config_file, profile):
        if(len(config_file) > 0 and len(profile) > 0):
            # profile == ConfigParser's "section" (e.g. [default])
            parser = ConfigParser()
            parser.read(config_file)
            if (parser.has_section(profile)):
                params = parser.items(profile)

                config = {}
                for param in params:
                    config[param[0]] = param[1]
            else:
                logging.error("Config file does not have configuration details for the specified profile.")
                raise ConfigFileError("Config file does not have configuration details for the specified profile.")
            return config
        else:
            logging.error("Config file does not appear to be set up correctly.")
            raise ConfigFileError("Config file does not appear to be set up correctly.")

    def __get_local_credentials(self, credentials_file, profile):
        if(len(credentials_file) > 0 and len(profile) > 0):
            # profile == ConfigParser's "section" (e.g. [default])
            parser = ConfigParser()
            parser.read(credentials_file)
            if (parser.has_section(profile)):
                params = parser.items(profile)

                creds = {}
                for param in params:
                    creds[param[0]] = param[1]
            else:
                logging.error("Credentials file does not have credentials for the specified profile.")
                raise CredentialsFileError("Credentials file does not have credentials for the specified profile.")
            return creds
        else:
            logging.error("Credentials file does not appear to be set up correctly.")
            raise CredentialsFileError("Credentials file does not appear to be set up correctly.")
    
    def resource(self, type):
        req_resource = getattr(sys.modules[__name__], type)
        return req_resource(Session())

class CredentialsFileError(Exception):
    pass

class ConfigFileError(Exception):
    pass