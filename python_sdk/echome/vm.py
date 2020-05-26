import requests
import logging

class base_echome:
    def __init__(self, session):
        self.base_url = f"{session.protocol}{session.server_url}/{session.api_version}/{self.namespace}"
        self.session = session

class Vm (base_echome):
    namespace = "vm"

    def describe_all(self):
        logging.debug(f"Making call to URL: {self.base_url}/describe/all")
        r = requests.get(f"{self.base_url}/describe/all")
        self.status_code = r.status_code
        return r.json()

    def describe(self, vm_id):
        logging.debug(f"Making call to URL: {self.base_url}/describe/{vm_id}")
        r = requests.get(f"{self.base_url}/describe/{vm_id}")
        self.status_code = r.status_code
        return r.json()

    #####
    # TODO
    #####
    def create(self, **kwargs):

        if "Tags" in kwargs:
            kwargs.update(self.unpack_tags(kwargs["Tags"]))
        
        logging.debug(kwargs)
        logging.debug(f"Making call to URL: {self.base_url}/create")
        r = requests.get(f"{self.base_url}/create", params=kwargs)
        self.status_code = r.status_code
        return r.json()
    
    def stop(self, vm_id):
        r = requests.get(f"{self.base_url}/stop/{vm_id}")
        self.status_code = r.status_code
        return r.json()
    
    def start(self, vm_id):
        r = requests.get(f"{self.base_url}/start/{vm_id}")
        self.status_code = r.status_code
        return r.json()

    def terminate(self, vm_id):
        r = requests.get(f"{self.base_url}/terminate/{vm_id}")
        self.status_code = r.status_code
        return r.json()
        
    def unpack_tags(self, tags: dict):
        tag_dict = {}
        num = 1
        tag_dict["Tags"] = "1"
        for tag_key in tags:
            tag_dict[f"Tag.{num}.Key"] = tag_key
            tag_dict[f"Tag.{num}.Value"] = tags[tag_key]
            num = num + 1
        return tag_dict

class Images (base_echome):
    namespace = "vm/images"
    class __guest (base_echome):
        namespace = "vm/images/guest"

        def describe_all(self):
            r = requests.get(f"{self.base_url}/all")
            self.status_code = r.status_code
            return r.json()
    
    class __user (base_echome):
        namespace = "vm/images/user"

        def describe_all(self):
            r = requests.get(f"{self.base_url}/all")
            self.status_code = r.status_code
            return r.json()
    
    def guest(self):
        return self.__guest(self.session)

    def user(self):
        return self.__user(self.session)

class InvalidImageType(Exception):
    pass
