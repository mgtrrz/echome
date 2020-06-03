import logging
import flask
import json
import base64
from markupsafe import escape
from flask import request, jsonify, url_for
from backend.vm_manager import VmManager
from backend.ssh_keystore import EchKeystore, KeyDoesNotExist, KeyNameAlreadyExists, PublicKeyAlreadyExists
from backend.instance_definitions import Instance, InvalidInstanceType
from backend.guest_image import GuestImage, UserImage, UserImageInvalidUser

app = flask.Flask(__name__)
app.config["DEBUG"] = True
logging.basicConfig(level=logging.DEBUG)

user = {
    "account_id": "12345",
    "account_user_id": "11119",
}

vm = VmManager()

@app.route('/', methods=['GET'])
def home():
    return {}


# curl 172.16.9.6:5000/v1/vm/create\?ImageId=gmi-fc1c9a62 \
# \&InstanceSize=standard.small \
# \&NetworkInterfacePrivateIp=172.16.9.10\/24 \
# \&NetworkInterfaceGatewayIp=172.16.9.1 \
# \&KeyName=echome
@app.route('/v1/vm/create', methods=['GET'])
def api_vm_create():
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
    
    network_type = request.args["NetworkType"] if "NetworkType" in request.args else ""
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
        vm_id = vm.createInstance(user, instanceDefinition, cloudinit_params, server_params, tags)
    except :
        return {"error": "There was an error when creating the instance."}, 500
    
    return jsonify({"vm_id": vm_id})


@app.route('/v1/vm/stop/<vm_id>', methods=['GET'])
def api_vm_stop(vm_id):
    return jsonify(vm.stopInstance(vm_id))


@app.route('/v1/vm/start/<vm_id>', methods=['GET'])
def api_vm_start(vm_id):
    return jsonify(vm.startInstance(vm_id))


@app.route('/v1/vm/terminate/<vm_id>', methods=['GET'])
def api_vm_terminate(vm_id):
    return jsonify(vm.terminateInstance(user, vm_id))


@app.route('/v1/vm/describe/all', methods=['GET'])
def api_vm_all():
    return jsonify(vm.getAllInstances(user))

@app.route('/v1/vm/describe/<vm_id>', methods=['GET'])
def api_vm_meta(vm_id=None):
    if not vm_id:
        return {"error": "VM ID must be provided."}, 400

    return jsonify(vm.getInstanceMetaData(user, vm_id))

@app.route('/v1/vm/modify/<vm_id>', methods=['POST'])
def api_vm_modification(vm_id=None):
    if not vm_id:
        return {"error": "VM ID must be provided."}, 400
    return jsonify(vm.getInstanceMetaData(user, vm_id))

####################
# Namespace: vm 
# Component: images
# vm/images

@app.route('/v1/vm/images/guest/all', methods=['GET'])
def api_guest_image_all():
    gmi = GuestImage()
    return jsonify(gmi.getAllImages())

@app.route('/v1/vm/images/user/all', methods=['GET'])
def api_user_image_all():
    vmi = UserImage()
    return jsonify(vmi.getAllImages())

####################
# Namespace: vm 
# Component: ssh_key
# vm/ssh_key

@app.route('/v1/vm/ssh_key/describe/all', methods=['GET'])
def api_ssh_keys_all():
    return jsonify(EchKeystore.get_all_keys(user))

@app.route('/v1/vm/ssh_key/describe/<ssh_key_name>', methods=['GET'])
def api_ssh_key(ssh_key_name=None):
    return jsonify(EchKeystore.get_key(user, ssh_key_name, get_public_key=False))

@app.route('/v1/vm/ssh_key/create', methods=['GET'])
def api_ssh_key_create():
    if not "KeyName" in request.args:
        return {"error": "KeyName must be provided when creating an ssh key."}, 400

    try:
        result = EchKeystore.create_key(user, request.args["KeyName"])
    except KeyNameAlreadyExists:
        return {"error": "Key (KeyName) with that name already exists."}, 400

    return jsonify(result)

@app.route('/v1/vm/ssh_key/delete/<ssh_key_name>', methods=['GET'])
def api_ssh_key_delete(ssh_key_name=None):
    if not ssh_key_name:
        return {"error": "KeyName must be provided when deleting an ssh key."}, 400

    try:
        result = EchKeystore.delete_key(user, ssh_key_name)
    except KeyDoesNotExist:
        return {"error": "Key (KeyName) with that name does not exist."}, 400

    return jsonify(result)

@app.route('/v1/vm/ssh_key/import', methods=['GET'])
def api_ssh_key_store():
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


app.run(host="0.0.0.0")