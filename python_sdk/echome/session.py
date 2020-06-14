import logging
import requests
import base64
import platform
import os
from configparser import ConfigParser
from os import getenv
from pathlib import Path
import sys
from .vm import Vm, Images, SshKey

default_echome_dir = ".echome"
default_echome_session_dir = ".echome/sess"
default_config_file = "config"
default_credential_file = "credentials"

default_profile = "default"

default_connection = "insecure"
default_format = "table"
api_version = "v1"

# Grabs the config and credentials from the user's home dir
# and establishes a connection with the server and authorization
class Session:

    def __init__(self):
        self.home_dir = str(Path.home())
        echome_dir = f"{self.home_dir}/{default_echome_dir}"

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

        self.format      = getenv("ECHOME_FORMAT", config_from_file["format"] if "format" in config_from_file else default_format)
        self.api_version = api_version

        self.base_url = f"{self.protocol}{self.server_url}/{self.api_version}"
        self.user_agent = f"ecHome_sdk/0.1.0 (Python {platform.python_version()}"
        self.token = None
        self.__get_session()
    
    # Login and retrieve a token
    def login(self):
        r = requests.post(f"{self.base_url}/auth/api/login", auth=(self.access_id, self.secret_key), headers=self.build_headers())
        response = r.json()
        if r.status_code == 200 and "token" in response:
            self.__save_session_token(response["token"])
            return True
        else:
            return False
    
    # Save session token
    def __save_session_token(self, session):
        sess_dir = f"{self.home_dir}/{default_echome_session_dir}"

        try:
            if not os.path.exists(sess_dir):
                os.makedirs(sess_dir)
        except Exception as e:
            print("Could not save sessions. Incorrect permissions?")
            raise Exception(e)

        token_file = f"{sess_dir}/token"
        with open(token_file, "w") as f:
            f.write(session)
            self.token = session
        
    # Get token
    def __get_session(self):
        sess_dir = f"{self.home_dir}/{default_echome_session_dir}"

        token_file = f"{sess_dir}/token"
        with open(token_file, "r") as f:
            contents = f.read()
        
        self.token = contents
        return contents

    
    def build_headers(self):
        return {
            'user-agent': self.user_agent,
            'x-authorization-id': self.access_id
        }

    def __get_local_config(self, config_file, profile):
        if(len(config_file) > 0 and len(profile) > 0):
            return self.__parse_file(config_file, profile)
        else:
            logging.error("Config file does not appear to be set up correctly.")
            raise ConfigFileError("Config file does not appear to be set up correctly.")

    def __get_local_credentials(self, credentials_file, profile):
        if(len(credentials_file) > 0 and len(profile) > 0):
            return self.__parse_file(credentials_file, profile)
        else:
            logging.error("Credentials file does not appear to be set up correctly.")
            raise CredentialsFileError("Credentials file does not appear to be set up correctly.")
    
    def client(self, type):
        """Return an API client for the requested type. e.g. .client("vm")"""
        requested_client = getattr(sys.modules[__name__], type)
        return requested_client(self)
    
    def __parse_file(self, file, profile):
         # profile == ConfigParser's "section" (e.g. [default])
        parser = ConfigParser()
        parser.read(file)
        if (parser.has_section(profile)):
            items = parser.items(profile)

            dict_items = {}
            for item in items:
                dict_items[item[0]] = item[1]
        else:
            logging.error(f"Parsed file {file} does not have items for the specified profile [{profile}].")
            raise CredentialsFileError(f"Parsed file {file} does not have items for the specified profile [{profile}].")
        return dict_items

class CredentialsFileError(Exception):
    pass

class ConfigFileError(Exception):
    pass