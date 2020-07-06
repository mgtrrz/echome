import logging
import flask
import json
import base64
import datetime
from markupsafe import escape
from flask import request, jsonify, url_for
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token,
    jwt_refresh_token_required, create_refresh_token,
    get_jwt_identity, fresh_jwt_required
)
from backend.vm_manager import VmManager
from backend.ssh_keystore import EchKeystore, KeyDoesNotExist, KeyNameAlreadyExists, PublicKeyAlreadyExists
from backend.instance_definitions import Instance, InvalidInstanceType
from backend.guest_image import GuestImage, UserImage, UserImageInvalidUser, InvalidImageId
from backend.user import User
from backend.database import Database, DbEngine
from backend.config import AppConfig
from functools import wraps

echomeConfig = AppConfig()

metadata_app = flask.Flask(__name__)
metadata_app.config["DEBUG"] = True
metadata_app.secret_key = echomeConfig.echome["api_secret"]
jwt = JWTManager(metadata_app)
logging.basicConfig(level=logging.DEBUG)


vm = VmManager()

@metadata_app.route('/', methods=['GET'])
def home():
    return {}

@metadata_app.route('/v1/ping', methods=['GET'])
def ping():
    return {"response": "pong"}


@metadata_app.route('/v1/auth/api/login', methods=['POST'])
def auth_api_login():
    auth = request.authorization

    incorrect_cred = jsonify({'error.auth': 'Incorrect credentials'}), 401

    if not auth or not auth.username or not auth.password:  
        return incorrect_cred

    db = DbEngine()
    dbsession = db.return_session()
    try:
        user = dbsession.query(User).filter_by(auth_id=auth.username).first()
    except Exception as e:
        logging.debug(e)
        return incorrect_cred
    
    if user is None:
        logging.debug(f"User was None: auth.username: {auth.username} - auth.password: {auth.password}")
        return incorrect_cred

    if user.check_password(str(auth.password).rstrip()):
        logging.debug("User successfully logged in.")
        ret = {
            'access_token': create_access_token(identity=auth.username, fresh=True, expires_delta=datetime.timedelta(minutes=10)),
            'refresh_token': create_refresh_token(identity=auth.username)
        }
        return jsonify(ret), 200

    return incorrect_cred


# The jwt_refresh_token_required decorator insures a valid refresh
# token is present in the request before calling this endpoint. We
# can use the get_jwt_identity() function to get the identity of
# the refresh token, and use the create_access_token() function again
# to make a new access token for this identity.
@metadata_app.route('/v1/auth/api/refresh', methods=['POST'])
@jwt_refresh_token_required
def auth_api_refresh():
    auth = request.authorization

    current_user = get_jwt_identity()
    print(current_user)
    ret = {
        'access_token': create_access_token(identity=current_user)
    }
    return jsonify(ret), 200



@metadata_app.route('/v1/auth/api/identity', methods=['GET'])
def auth_identity():
    current_user = get_jwt_identity()
    print(current_user)
    pass

def return_calling_user():
    print("Grabbing returning user")
    db = DbEngine()
    dbsession = db.return_session()
    current_user = get_jwt_identity()
    try:
        user = dbsession.query(User).filter_by(auth_id=current_user).first()
    except:  
        return jsonify({'auth.error': 'Token is invalid'}), 401
    
    if user is None:
        return jsonify({'auth.error': 'Invalid user'}), 401

    return user

# def get_instance_metadata_by_ip(ip):
#     session = DbEngine().return_session()

#     user_instances = Database().user_instances

#     ip = f"{ip}/24"

#     records = session.query().filter(
#         user_instances.attached_interfaces["config_at_launch"]["private_ip"].astext == ip
#     ).all()

#     select_stmt = select(columns).where(self.db.user_instances.c.account == user_obj.account)
#     rows = self.db.connection.execute(select_stmt).fetchall()
#     print(records)


USERDATA_TEMPLATE = """\
#cloud-config
hostname: {{hostname}}
local-hostname: {{hostname}}
fqdn: {{hostname}}.localdomain
manage_etc_hosts: true
password: {{mdserver_password}}
chpasswd: { expire: False }
ssh_pwauth: True
ssh_authorized_keys:
    - {{public_key_default}}
"""


class MetadataHandler(object):
    instance_id = None
    vm_metadata = None

    # Get VM metadata from remote_addr
    def __init__(self):
        vm = VmManager()

        logging.debug(f"Searching for {request.remote_addr}/24")
        self.vm_metadata = vm.get_instance_metadata_by_ip(f"{request.remote_addr}/24")
        if self.vm_metadata:
            self.instance_id = self.vm_metadata["instance_id"]
        else:
            logging.error(f"Could not find VM metadata for calling IP: {request.remote_addr}")
            raise

    def _get_mgmt_mac(self):
        lease_file = '/var/lib/libvirt/dnsmasq/default.leases'
        client_host = request.remote_addr
        for line in open(lease_file):
            line_parts = line.split(" ")
            if client_host == line_parts[2]:
                mac = line_parts[1]
                return mac

    def _get_hostname_from_libvirt_domain(self):
        mac_addr = self._get_mgmt_mac()
        domain_mac_db = open('/etc/libvirt/qemu_db').readline()
        json_db = json.loads(domain_mac_db)
        domain_name = json_db.get(mac_addr)
        return domain_name

    def gen_metadata(self):
        res = ["instance-id",
               "hostname",
               "public-keys",
               ""]
        return self.format_response(res)

    def gen_userdata(self):
        config = bottle.request.app.config
        config['public_key_default'] = config['public-keys.default']
        config['mdserver_password'] = config['mdserver.password']
        config['hostname'] = self.gen_hostname().strip('\n')
        user_data = template(USERDATA_TEMPLATE, **config)
        return self.format_response(user_data)

    def generate_hostname_from_ip(self):
        #client_host = request.remote_addr
        prefix = "ip"
        ip_str = "-".join(request.remote_addr.split('.'))
        res = f"{prefix}-{ip_str}"
        return self.format_response(res)

    def get_hostname(self):
        # try:
        #     hostname = self._get_hostname_from_libvirt_domain()
        # except Exception as e:
        #     logging.error("Exception %s" % e)
        #     return self.gen_hostname_old()

        # if not hostname:
        #     return self.gen_hostname_old()
        hostname = self.generate_hostname_from_ip()
        return hostname

    def get_vm_id(self):
        return self.format_response(self.instance_id)

    # Get the authorized ssh keys for this instance
    # root directory for /meta-data/public-keys/
    def get_public_key_names(self):
        pubkeys = self._public_key_list()
        i = 0
        keys = []
        for pubkey in pubkeys:
            keys.append(f"{i}={pubkey}")

        return self.format_response(keys)
    
    def get_public_key(self, index: int):
        pubkeys = self._public_key_list()
        if index > len(pubkeys):
            return None

        return self.format_response(EchKeystore.get_public_key_vm_metadata(pubkeys[index], self.vm_metadata))

    def _public_key_list(self):
        return self.vm_metadata["key_name"].split(",")

    def format_response(self, res):
        if isinstance(res, list):
            return "\n".join(res)
        elif isinstance(res, str):
            return f"{res}\n"




@metadata_app.route('/meta-data/')
def metadata():
    md_handler = MetadataHandler()
    return md_handler.gen_metadata()

@metadata_app.route('/meta-data/<key>/')
def metadata_info(key=None):
    try:
        md_handler = MetadataHandler()
    except:
        return "Unable to retrieve VM metadata from request IP.", 400

    if key == "hostname":
        return md_handler.get_hostname()
    elif key == "instance-id":
        return md_handler.get_vm_id()
    elif key == "public-keys":
        return md_handler.get_public_key_names()
    else:
        return "Unknown type requested", 404

@metadata_app.route('/meta-data/public-keys/<index>/')
def metadata_public_key_type(index):
    try:
        md_handler = MetadataHandler()
    except:
        return "Unable to retrieve VM metadata from request IP.", 400

    key = md_handler.get_public_key(int(index))
    if key is None:
        return "Not found", 404

    return "openssh-key\n"

@metadata_app.route('/meta-data/public-keys/<index>/openssh-key/')
def metadata_public_keys(index):
    try:
        md_handler = MetadataHandler()
    except:
        return "Unable to retrieve VM metadata from request IP.", 400

    return md_handler.get_public_key(int(index))


@metadata_app.route('/user-data/')
def user_data():
    return {"response": "user-data"}


if __name__ == "__main__":
    metadata_app.run(host="0.0.0.0")