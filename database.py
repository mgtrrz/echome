import psycopg2
import logging
from configparser import ConfigParser

SECTION_NAME = "echome_db"

class Database:

    def __init__(self, config_file_path):
        self.db_connection = self.get_connection_by_config(config_file_path)

    def get_connection_by_config(self, config_file_path):
        if(len(config_file_path) > 0 and len(SECTION_NAME) > 0):

            parser = ConfigParser()
            parser.read(config_file_path)

            if(parser.has_section(SECTION_NAME)):

                params = parser.items(SECTION_NAME)
                db_conn_dict = {}

                for param in params:
                    key = param[0]
                    value = param[1]
                    db_conn_dict[key] = value

                return psycopg2.connect(**db_conn_dict)
        else:
            logging.error("Cannot make a database connection without config file path.")