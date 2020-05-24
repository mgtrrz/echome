import logging
from configparser import ConfigParser
from os import getenv
from pathlib import Path

default_echome_dir = ".echome"
default_credential_file = "credentials"
default_profile = "default"

class Session:

    def __init__(self):
        home_dir = str(Path.home())
        cred_file  = f"{home_dir}/{default_echome_dir}/{default_credential_file}"

        self.current_profile = getenv("ECHOME_PROFILE", default_profile)

        try:
            creds_from_file = self.__get_local_credentials(cred_file, self.current_profile)
        except CredentialsFileError as e:
            raise CredentialsFileError(e)

        self.access_id  = getenv("ECHOME_ACCESS_ID", creds_from_file["access_id"])
        self.secret_key = getenv("ECHOME_SECRET_KEY", creds_from_file["secret_key"])


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

class CredentialsFileError(Exception):
    pass