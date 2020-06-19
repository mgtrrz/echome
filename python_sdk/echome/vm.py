import requests
import logging
import base64
import json
from .response import Response

class base_resource:
    namespace = ""

    def __init__(self, session, item_id=None):
        self.init_session(session)
    
    def init_session(self, session, namespace=""):
        if namespace:
            self.namespace = namespace
        self.base_url = f"{session.base_url}/{self.namespace}"
        self.session = session
    
    def build_headers(self, type="access"):

        logging.debug("Preparing Requests headers for normal access request")
        headers = {
            'user-agent': self.session.user_agent,
            'Authorization': f"Bearer {self.session.token}"
        }
        
        return headers
    
    def request_url(self, url_namespace, method="get", **kwargs):
        # method here defines the request type to make. 'get' == requests.get, 'post', requests.post, etc.
        try_refresh = False
        try_login = False
        x = 0
        while True:
            logging.debug(f"Calling: {self.base_url}{url_namespace}")
            response = getattr(requests, method)(f"{self.base_url}{url_namespace}", headers=self.build_headers(), params=kwargs)
            logging.debug(f"Got response code: {response.status_code}")

            if response.status_code == 401:
                # Try refreshing the token
                logging.debug("Access token has expired, attempting refresh")
                if self.session.refresh_token() and try_refresh is False:
                    # The method returned True, it should be good to retry.
                    try_refresh = True
                    pass
                else:
                    # If we can't refresh, the refresh token is expired, try logging in to get new token/refresh.
                    if self.session.login() and try_login is False:
                        # try the original call again
                        try_login = True
                        pass
                    else:
                        logging.debug("Unable to login, giving up at this point.")
                        Response.unauthorized_response("Unable to successfully authorize with ecHome server.", exit=True)

            if response.status_code != 401:
                break

            if x > 5:
                logging.warn("While True loop for making a request exceeded 5 loops. This should not have happened.")
                raise Exception("Reached an infinite loop state while making a request that should not have happened. Exiting for safety.")
            x += 1
        
        if response.status_code == 200 or response.status_code == 404:
            return response
        else:
            logging.debug(f"Unexpected response from the server: {response.status_code}")
            Response.unexpected_response(f"Unexpected response from the server: {response.json()}", exit=True)


    
    def unpack_tags(self, tags: dict):
        tag_dict = {}
        num = 1
        tag_dict["Tags"] = "1"
        for tag_key in tags:
            tag_dict[f"Tag.{num}.Key"] = tag_key
            tag_dict[f"Tag.{num}.Value"] = tags[tag_key]
            num = num + 1
        return tag_dict

class Vm (base_resource):
    namespace = "vm"

    def describe_all(self, json_response=True):
        r = self.request_url("/describe/all")
        self.status_code = r.status_code
        self.raw_json_response = r.json()
        return r.json()

    def describe(self, vm_id, json_response=True):
        r = self.request_url(f"/describe/{vm_id}")
        self.status_code = r.status_code
        self.raw_json_response = r.json()

        if r.status_code != 200:
            # TODO: Error handling
            return r.json()

        resp = json.loads(r.text)
        for vm in resp:
            instobj = Instance(
                self.session, 
                self.namespace, 
                attached_interfaces = vm["attached_interfaces"],
                created = vm["created"],
                host = vm["host"],
                instance_id = vm["instance_id"],
                instance_size = f"{vm['instance_type']}.{vm['instance_size']}",
                key_name = vm["key_name"],
                state = vm["state"],
                tags = vm["tags"]
            )
        if not json_response:
            return instobj
        else:
            return resp
    
    def set_metadata(self, **kwargs):
        self.vm_id = kwargs.get("instance_id")
        self.attached_interfaces = kwargs.get("attached_interfaces", "")
        self.host = kwargs.get("host", "")
        self.created = kwargs.get("created", "")
        self.key_name = kwargs.get("key_name", "")
        self.instance_size = kwargs.get('instance_size', "")
        self.state = kwargs.get("state", {})
        self.tags = kwargs.get("tags", {})
        
    def create(self, **kwargs):
        if "Tags" in kwargs:
            kwargs.update(self.unpack_tags(kwargs["Tags"]))
        
        #r = requests.get(f"{self.base_url}/create", headers=self.build_headers(), params=kwargs)
        r = self.request_url("/create", "post", **kwargs)
        self.status_code = r.status_code
        return r.json()
    
    def stop(self, id=""):
        if not id:
            id = self.vm_id
        
        #r = requests.get(f"{self.base_url}/stop/{id}", headers=self.build_headers())
        r = self.request_url(f"/stop/{id}", "post")
        self.status_code = r.status_code
        return r.json()
    
    def start(self, id=""):
        if not id:
            id = self.vm_id
        #r = requests.get(f"{self.base_url}/start/{id}", headers=self.build_headers())
        r = self.request_url(f"/start/{id}", "post")
        self.status_code = r.status_code
        return r.json()

    def terminate(self, id=""):
        if not id:
            id = self.vm_id
        #r = requests.get(f"{self.base_url}/terminate/{id}", headers=self.build_headers())
        r = self.request_url(f"/terminate/{id}", "post")
        self.status_code = r.status_code
        return r.json()
    
    def __str__(self):
        if self.vm_id:
            return self.vm_id
        else:
            return "GenericVmObject"
        

class Instance (base_resource):
    def __init__(self, session, namespace, **kwargs):
        self.vm_id = kwargs.get("instance_id")
        self.attached_interfaces = kwargs.get("attached_interfaces", "")
        self.host = kwargs.get("host", "")
        self.created = kwargs.get("created", "")
        self.key_name = kwargs.get("key_name", "")
        self.instance_size = kwargs.get('instance_size', "")
        self.state = kwargs.get("state", {})
        self.tags = kwargs.get("tags", {})

        self.namespace = namespace
        self.init_session(session)
    
    def __str__(self):
        return self.vm_id

# TODO: Return image objects

class Images (base_resource):
    class __guest (base_resource):
        namespace = "vm/images/guest"

        def describe_all(self):
            #r = requests.get(f"{self.base_url}/describe-all")
            r = self.request_url(f"/describe-all")
            self.status_code = r.status_code
            return r.json()

        def describe(self, id):
            #r = requests.get(f"{self.base_url}/describe/{id}")
            r = self.request_url(f"/describe/{id}")
            self.status_code = r.status_code
            return r.json()

        def register(self, **kwargs):
            #r = requests.post(f"{self.base_url}/register", params=kwargs)
            r = self.request_url(f"/register", method="post", **kwargs)
            self.status_code = r.status_code
            return r.json()

    
    class __user (base_resource):
        namespace = "vm/images/user"

        def describe_all(self):
            #r = requests.get(f"{self.base_url}/describe-all")
            r = self.request_url(f"/describe-all")
            self.status_code = r.status_code
            return r.json()
    
    def guest(self):
        return self.__guest(self.session)

    def user(self):
        return self.__user(self.session)


class InvalidImageType(Exception):
    pass

class UnauthorizedResponse(Exception):
    pass

class UnexpectedResponse(Exception):
    pass

class SshKey (base_resource):
    namespace = "vm/ssh_key"

    def describe_all(self):
        #r = requests.get(f"{self.base_url}/describe/all")
        r = self.request_url(f"/describe/all")
        self.status_code = r.status_code
        return r.json()

        # if r.status_code == 200:
        #     json_res = json.loads(r.text)
        #     keys = []
        #     for key in json_res:
        #         obj = SshKeyObject(
        #             self.session, 
        #             self.namespace,
        #             fingerprint=key["fingerprint"],
        #             key_id=key["key_id"],
        #             key_name=key["key_name"]
        #         )
        #         keys.append(obj)
        # return keys
    
    def describe(self, KeyName):
        #r = requests.get(f"{self.base_url}/describe/{KeyName}")
        r = self.request_url(f"/describe/{KeyName}")

        self.status_code = r.status_code
        return r.json()

        # if r.status_code == 200:
        #     json_res = json.loads(r.text)
        #     for key in json_res:
        #         obj = SshKeyObject(
        #             self.session, 
        #             self.namespace,
        #             fingerprint=key["fingerprint"],
        #             key_id=key["key_id"],
        #             key_name=key["key_name"]
        #         )
        # return obj
    
    def create(self, KeyName):
        #r = requests.get(f"{self.base_url}/create", params={"KeyName": KeyName})
        r = self.request_url(f"/create", method="post", KeyName=KeyName)
        self.status_code = r.status_code
        return r.json()
    
    def delete(self, KeyName):
        #r = requests.get(f"{delf.base_url}/delete/{KeyName}")
        r = self.request_url(f"/delete/{KeyName}", method="post")
        self.status_code = r.status_code
        return r.json()
    
    def import_key(self, KeyName, PublicKey):

        args = {
            "KeyName": KeyName,
            "PublicKey": base64.urlsafe_b64encode(PublicKey)
        }
        #r = requests.get(f"{self.base_url}/import", params=args)
        r = self.request_url(f"/import", method="post", params=args)
        self.status_code = r.status_code
        return r.json()

class SshKeyObject(base_resource):

    def __init__(self, session, namespace, **kwargs):
        self.fingerprint = kwargs["fingerprint"]
        self.key_id = kwargs["key_id"]
        self.key_name = kwargs["key_name"]
        self.namespace = namespace
        self.init_session(session)
    
    def __str__(self):
        return self.key_name
    
    def delete(self):
        r = requests.get(f"{self.base_url}/delete/{self.key_name}")
        self.status_code = r.status_code
        return r.json()