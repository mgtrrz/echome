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
from backend.database import DbEngine
from backend.config import AppConfig
from functools import wraps

echomeConfig = AppConfig()

app = flask.Flask(__name__)
app.config["DEBUG"] = True
app.secret_key = echomeConfig.echome["api_secret"]
jwt = JWTManager(app)
logging.basicConfig(level=logging.DEBUG)


vm = VmManager()

@app.route('/', methods=['GET'])
def home():
    return {}

@app.route('/v1/ping', methods=['GET'])
def ping():
    return {"response": "pong"}


@app.route('/v1/auth/api/login', methods=['POST'])
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
@app.route('/v1/auth/api/refresh', methods=['POST'])
@jwt_refresh_token_required
def auth_api_refresh():
    auth = request.authorization

    current_user = get_jwt_identity()
    print(current_user)
    ret = {
        'access_token': create_access_token(identity=current_user)
    }
    return jsonify(ret), 200



@app.route('/v1/auth/api/identity', methods=['GET'])
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

# curl 172.16.9.6:5000/v1/vm/create\?ImageId=gmi-fc1c9a62 \
# \&InstanceSize=standard.small \
# \&NetworkInterfacePrivateIp=172.16.9.10\/24 \
# \&NetworkInterfaceGatewayIp=172.16.9.1 \
# \&KeyName=echome
@app.route('/v1/vm/create', methods=['POST'])
@jwt_required
def api_vm_create():
    user = return_calling_user()
    if not "ImageId" in request.args:
        return {"error": "ImageId must be provided when creating a VM."}, 400
    
    if not "InstanceSize" in request.args:
        return {"error": "InstanceSize must be provided when creating a VM."}, 400
    
    iTypeSize = request.args["InstanceSize"].split(".")
    try:
        instanceDefinition = Instance(iTypeSize[0], iTypeSize[1])
    except InvalidInstanceType:
        return {"error": "Provided InstanceSize is not a valid type or size."}, 400

    tags = {}
    if "Tags" in request.args:
        there_are_tags = True
        x = 1
        while there_are_tags:
            if f"Tag.{x}.Key" in request.args:

                keyname = request.args[f"Tag.{x}.Key"]
                if f"Tag.{x}.Value" in request.args:
                    value = request.args[f"Tag.{x}.Value"]
                else:
                    value = ""

                tags[keyname] = value
            else:
                there_are_tags = False
                continue
            x = x + 1

    dsize = request.args["DiskSize"] if "DiskSize" in request.args else "10G"
    
    network_type = request.args["NetworkType"] if "NetworkType" in request.args else "BridgeToLan"
    priv_ip = request.args["NetworkInterfacePrivateIp"] if "NetworkInterfacePrivateIp" in request.args else ""
    gateway_ip = request.args["NetworkInterfaceGatewayIp"] if "NetworkInterfaceGatewayIp" in request.args else ""
    
    keyname = ""
    pub_key = ""
    if "KeyName" in request.args:
        try:
            keyname = request.args["KeyName"]
            key_meta = EchKeystore.get_key(user, keyname)
            pub_key = key_meta[0]["public_key"]
        except KeyDoesNotExist:
            return {"error": "Provided KeyName does not exist."}, 400
    
    cloudinit_params = {
        "cloudinit_key_name": keyname,
        "cloudinit_public_key": pub_key,
        "network_type": network_type,
        "private_ip": priv_ip,
        "gateway_ip": gateway_ip
    }
    server_params = {
        "image_id": request.args["ImageId"],
        "disk_size": dsize,
    }

    try:
        vm_id = vm.createVirtualMachine(user, instanceDefinition, cloudinit_params, server_params, tags)
    except Exception as e:
        logging.debug(f"Exception hit: {e}")
        return {"error": "There was an error when creating the instance."}, 500
    
    return jsonify({"vm_id": vm_id})


@app.route('/v1/vm/stop/<vm_id>', methods=['POST'])
@jwt_required
def api_vm_stop(vm_id):
    user = return_calling_user()
    return jsonify(vm.stopInstance(vm_id))


@app.route('/v1/vm/start/<vm_id>', methods=['POST'])
@jwt_required
def api_vm_start(vm_id):
    user = return_calling_user()
    return jsonify(vm.startInstance(vm_id))


@app.route('/v1/vm/terminate/<vm_id>', methods=['POST'])
@jwt_required
def api_vm_terminate(vm_id):
    user = return_calling_user()
    return jsonify(vm.terminateInstance(user, vm_id))

@app.route('/v1/vm/describe/all', methods=['GET'])
@jwt_required
def api_vm_all():
    user = return_calling_user()
    return jsonify(vm.getAllInstances(user))

@app.route('/v1/vm/describe/<vm_id>', methods=['GET'])
@jwt_required
def api_vm_meta(vm_id=None):
    user = return_calling_user()
    if not vm_id:
        return {"error": "VM ID must be provided."}, 400

    return jsonify(vm.getInstanceMetaData(user, vm_id))

@app.route('/v1/vm/modify/<vm_id>', methods=['POST'])
@jwt_required
def api_vm_modification(vm_id=None):
    user = return_calling_user()
    if not vm_id:
        return {"error": "VM ID must be provided."}, 400
    return jsonify(vm.getInstanceMetaData(user, vm_id))


@app.route('/v1/vm/instance_types/describe-all', methods=['POST'])
def api_instance_types_describe_all():
    
    return jsonify(vm.getInstanceMetaData(user, vm_id))

####################
# Namespace: vm 
# Component: images
# vm/images

@app.route('/v1/vm/images/guest/describe-all', methods=['GET'])
def api_guest_image_all():
    gmi = GuestImage()
    return jsonify(gmi.getAllImages())

@app.route('/v1/vm/images/guest/describe/<img_id>', methods=['GET'])
def api_guest_image_describe(img_id=None):
    if not img_id:
        return {"error": "Image Id must be provided."}, 400
    gmi = GuestImage()
    try: 
        return jsonify(gmi.getImageMeta(img_id))
    except InvalidImageId as e:
        return {"error": "Image Id does not exist."}, 404

@app.route('/v1/vm/images/guest/register', methods=['POST'])
@jwt_required
def api_guest_image_register():
    user = return_calling_user()
    gmi = GuestImage()

    if not "ImagePath" in request.args:
        return {"error": "ImagePath must be provided when registering a guest image."}, 400
    
    if not "ImageName" in request.args:
        return {"error": "ImageName must be provided when registering a guest image."}, 400 
    
    if not "ImageDescription" in request.args:
        return {"error": "ImageDescription must be provided when registering a guest image."}, 400 

    try: 
        img_id = gmi.registerImage(request.args["ImagePath"], request.args["ImageName"], request.args["ImageDescription"])
    except InvalidImagePath:
        return {"error": "ImagePath: Provided path is not valid or file does not exist."}, 400
    except InvalidImageAlreadyExists:
        return {"error": "ImagePath: Image with this file path already exists."}, 400

    new_img = {"guest_image_id": img_id}
    return jsonify(new_img)

@app.route('/v1/vm/images/user/describe-all', methods=['GET'])
@jwt_required
def api_user_image_all():
    user = return_calling_user()
    vmi = UserImage(user)
    return jsonify(vmi.getAllImages())

####################
# Namespace: vm 
# Component: ssh_key
# vm/ssh_key

@app.route('/v1/vm/ssh_key/describe/all', methods=['GET'])
@jwt_required
def api_ssh_keys_all():
    user = return_calling_user()
    return jsonify(EchKeystore.get_all_keys(user))

@app.route('/v1/vm/ssh_key/describe/<ssh_key_name>', methods=['GET'])
@jwt_required
def api_ssh_key(ssh_key_name=None):
    user = return_calling_user()
    return jsonify(EchKeystore.get_key(user, ssh_key_name, get_public_key=False))

@app.route('/v1/vm/ssh_key/create', methods=['POST'])
@jwt_required
def api_ssh_key_create():
    user = return_calling_user()

    if not "KeyName" in request.args:
        return {"error": "KeyName must be provided when creating an ssh key."}, 400

    try:
        result = EchKeystore.create_key(user, request.args["KeyName"])
    except KeyNameAlreadyExists:
        return {"error": "Key (KeyName) with that name already exists."}, 400

    return jsonify(result)

@app.route('/v1/vm/ssh_key/delete/<ssh_key_name>', methods=['POST'])
@jwt_required
def api_ssh_key_delete(ssh_key_name=None):
    user = return_calling_user()

    if not ssh_key_name:
        return {"error": "KeyName must be provided when deleting an ssh key."}, 400

    try:
        result = EchKeystore.delete_key(user, ssh_key_name)
    except KeyDoesNotExist:
        return {"error": "Key (KeyName) with that name does not exist."}, 400

    return jsonify(result)

@app.route('/v1/vm/ssh_key/import', methods=['POST'])
@jwt_required
def api_ssh_key_store():
    user = return_calling_user()

    if not "KeyName" in request.args:
        return {"error": "KeyName must be provided when importing an ssh key."}, 400

    if not "PublicKey" in request.args:
        return {"error": "PublicKey must be provided when importing an ssh key."}, 400
    
    #Base64 decode:
    try:
        pub_key = base64.b64decode(request.args["PublicKey"])
        pub_key = pub_key.decode()
    except TypeError:
        return {"error": "Could not decode PublicKey string. Retry with a base64 encoded PublicKey string or verify string is properly base64 encoded."}, 400

    try:
        results = EchKeystore.store_key(user, request.args["KeyName"], pub_key)
    except KeyNameAlreadyExists:
        return {"error": "Key (KeyName) with that name already exists."}, 400
    except PublicKeyAlreadyExists:
        return {"error": "Public Key (PublicKey) with that fingerprint already exists."}, 400

    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0")