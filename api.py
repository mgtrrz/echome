import logging
import flask
import json
from markupsafe import escape
from flask import request, jsonify, url_for
from vm_manager import vmManager
from database import Database
from ssh_keystore import EchKeystore, KeyDoesNotExist
from instance_definitions import Instance, InvalidInstanceType
from guest_image import GuestImage

app = flask.Flask(__name__)
app.config["DEBUG"] = True

user = {
    "account_id": "12345",
    "account_user_id": "11119",
}

vm = vmManager()

@app.route('/', methods=['GET'])
def home():
    return {}

# curl -X POST 172.16.9.6:5000/v1/vm/create\?ImageId=gmi-fc1c9a62 \
# \&InstanceSize=standard.small \
# \&NetworkInterfacePrivateIp=172.16.9.10\/24 \
# \&NetworkInterfaceGatewayIp=172.16.9.1 \
# \&KeyName=test_key
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

    dsize = request.args["DiskSize"] if "DiskSize" in request.args else "10G"
    tags = request.args["Tags"] if "Tags" in request.args else {}

    if "NetworkInterfacePrivateIp" in request.args:
        priv_ip = request.args["NetworkInterfacePrivateIp"]
    else:
        priv_ip = ""
    
    if "NetworkInterfaceGatewayIp" in request.args:
        gateway_ip = request.args["NetworkInterfaceGatewayIp"]
    else:
        gateway_ip = ""
    

    if "KeyName" in request.args:
        try:
            keyname = request.args["KeyName"]
            key_meta = EchKeystore.get_key(user, keyname)
            pub_key = key_meta["public_key"]
        except KeyDoesNotExist:
            return {"error": "Provided KeyName does not exist."}, 400
    else:
        keyname = ""
        pub_key = ""
    
    cloudinit_params = {
        "cloudinit_key_name": keyname,
        "cloudinit_public_key": pub_key,
        "network": "local", # local, private, public?
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
    
    return jsonify({"success": True, "vm_id": vm_id})


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
    
    print(request)

    
    return jsonify(vm.getInstanceMetaData(user, vm_id))

app.run(host="0.0.0.0")