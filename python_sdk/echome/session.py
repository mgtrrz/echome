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

    _token = None
    _refresh = None

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

        # try retrieving session tokens we already have by reading the files and setting the variables
        self.load_local_tokens()
        # If the token variable is still enpty, log in to set them.
        if self._token is None:
            self.login()

    
    # Login and retrieve a token
    def login(self):
        logging.debug("Logging in to ecHome server")
        r = requests.post(f"{self.base_url}/auth/api/login", auth=(self.access_id, self.secret_key), headers=self.build_headers())
        response = r.json()
        if r.status_code == 200 and "access_token" in response:
            self.token = response["access_token"]
            self.refresh = response["refresh_token"]
            return True
        else:
            return False
    
    # refresh the token
    def refresh_token(self):
        r = requests.post(f"{self.base_url}/auth/api/refresh", headers=self.build_headers(self.refresh))
        response = r.json()
        if r.status_code == 200 and "access_token" in response:
            self.token = response["access_token"]
            return True
        else:
            return False
    
    def load_local_tokens(self):
        self.token
        self.refresh
    
    @property
    def token(self): 
        logging.debug("Getting Token") 
        if self._token is None:
            logging.debug("Session _token is empty, attempting to retrieve from local file.")
            self._token = self.__get_session()

        if self._token is None:
            logging.debug("Session _token is still empty!")
        return self._token 
    
    # a setter function 
    @token.setter 
    def token(self, a): 
        logging.debug("Setting Token") 
        self._token = self.__save_session_token(a)
    

    @property
    def refresh(self): 
        logging.debug("Getting Refresh Token") 
        if self._refresh is None:
            logging.debug("Refresh _token is empty, attempting to retrieve from local file.")
            self._refresh = self.__get_session(type="refresh")

        if self._refresh is None:
            logging.debug("Refresh _token is still empty!")
        return self._refresh 
    
    # a setter function 
    @refresh.setter 
    def refresh(self, a): 
        logging.debug("Setting Refresh Token") 
        self._refresh = self.__save_session_token(a, type="refresh")
    
    # Save session token
    def __save_session_token(self, token, type="access"):
        sess_dir = f"{self.home_dir}/{default_echome_session_dir}"

        try:
            if not os.path.exists(sess_dir):
                os.makedirs(sess_dir)
        except Exception as e:
            print("Could not save sessions. Incorrect permissions?")
            raise Exception(e)

        if type == "access":
            fname = "token"
        elif type == "refresh":
            fname = "refresh"
        else:
            raise Exception("Unknown type specified when calling save_session_token")

        token_file = f"{sess_dir}/{fname}"
        with open(token_file, "w") as f:
            f.write(token)
        
        return token
        
    # Get token
    def __get_session(self, type="access"):
        sess_dir = f"{self.home_dir}/{default_echome_session_dir}"

        if type == "access":
            fname = "token"
        elif type == "refresh":
            fname = "refresh"
        else:
            raise Exception("Unknown type specified when calling get_session_token")

        token_file = f"{sess_dir}/{fname}"
        try:
            with open(token_file, "r") as f:
                contents = f.read()
        except:
            return None
        
        return contents

    
    def build_headers(self, token=None):
        header = {
            'user-agent': self.user_agent
        }

        if token:
            header["Authorization"] = f"Bearer {token}"
        
        return header

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