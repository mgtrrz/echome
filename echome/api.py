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
    get_jwt_identity, fresh_jwt_required, jwt_optional
)
from backend.config import ecHomeConfig
from backend.vm_manager import VmManager, InvalidLaunchConfiguration, LaunchError
from backend.kube_manager import KubeManager, ClusterDoesNotExist, ServerError
from backend.ssh_keystore import KeyStore, KeyDoesNotExist, KeyNameAlreadyExists, PublicKeyAlreadyExists
from backend.instance_definitions import Instance, InvalidInstanceType
from backend.guest_image import ImageManager, GuestImage, UserImage, UserImageInvalidUser, \
    InvalidImageId, InvalidImagePath, InvalidImageAlreadyExists
from backend.user import User, UserManager
from backend.database import dbengine
from backend.vnet import VirtualNetwork, InvalidNetworkName, InvalidNetworkType, InvalidNetworkConfiguration
from functools import wraps


app = flask.Flask(__name__)
app.config["DEBUG"] = True
app.secret_key = ecHomeConfig.EcHome().api_secret

jwt = JWTManager(app)
logging.basicConfig(filename=ecHomeConfig.EcHome().api_server_log, level=logging.DEBUG)

logger = logging.getLogger()
logger.setLevel(level=logging.DEBUG)

# Convert parameter tags (e.g. Tag.1.Key=Name, Tag.1.Value=MyVm, Tag.2.Key=Env, etc.)
# to a dictionary e.g. {"Name": "MyVm", "Env": "stage"}
def unpack_tags(request_args=None):
    dict_tags = {}    
    there_are_tags = True
    x = 1
    while there_are_tags:
        if f"Tag.{x}.Key" in request_args:
            keyname = request_args[f"Tag.{x}.Key"]
            if f"Tag.{x}.Value" in request_args:
                value = request_args[f"Tag.{x}.Value"]
            else:
                value = ""

            dict_tags[keyname] = value
        else:
            there_are_tags = False
            continue
        x = x + 1
    
    return dict_tags

vm = VmManager()

@app.route('/', methods=['GET'])
def home():
    return {}

@app.route('/v1/ping', methods=['GET'])
def ping():
    return jsonify({"response": "pong"})


@app.route('/v1/auth/api/login', methods=['POST'])
def auth_api_login():
    auth = request.authorization

    incorrect_cred = jsonify({'error.auth': 'Incorrect credentials'}), 401

    if not auth or not auth.username or not auth.password:  
        return incorrect_cred

    try:
        user = dbengine.session.query(User).filter_by(auth_id=auth.username).first()
    except Exception as e:
        logging.debug(e)
        return incorrect_cred
    
    if user is None:
        logging.debug(f"User was None: auth.username: {auth.username} - auth.password: {auth.password}")
        return incorrect_cred

    if user.check_password(str(auth.password).rstrip()):
        logging.debug("User successfully logged in.")
        ret = {
            'access_token': create_access_token(
                identity=auth.username, 
                fresh=True, 
                expires_delta=datetime.timedelta(minutes=10)
            ),
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
    logging.debug("Grabbing user from request")
    current_user = get_jwt_identity()
    logging.debug(current_user)

    try:
        user = UserManager().get_user(auth_id=current_user)
    except:  
        return jsonify({'auth.error': 'Token is invalid'}), 401
    
    if user is None:
        return jsonify({'auth.error': 'Invalid user'}), 401

    return user

####################
# Namespace: vm 
# vm/

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
    
    if not "NetworkProfile" in request.args:
        return {"error": "NetworkProfile must be provided when creating a VM."}, 400
    
    if "ServiceKey" in request.args:
        return {"error": "Unrecognized option."}, 400
    
    iTypeSize = request.args["InstanceSize"].split(".")
    try:
        instanceDefinition = Instance(iTypeSize[0], iTypeSize[1])
    except InvalidInstanceType:
        return {"error": "Provided InstanceSize is not a valid type or size."}, 400

    tags = unpack_tags(request.args)

    disk_size = request.args["DiskSize"] if "DiskSize" in request.args else "10G"
    
    key_name = None
    if "KeyName" in request.args:
        try:
            KeyStore().get(user, request.args["KeyName"])
            key_name = request.args["KeyName"]
        except KeyDoesNotExist:
            return {"error": "Provided KeyName does not exist."}, 400

    try:
        vm_id = vm.create_vm(
            user=user, 
            instanceType=instanceDefinition, 
            Tags=tags,
            KeyName=key_name,
            NetworkProfile=request.args["NetworkProfile"],
            PrivateIp=request.args["PrivateIp"] if "PrivateIp" in request.args else "",
            ImageId=request.args["ImageId"],
            DiskSize=disk_size    
        )
    except InvalidLaunchConfiguration as e:
        logging.debug(e)
        return {"error": "A supplied value was invalid and could not successfully build the virtual machine."}, 400
    except LaunchError as e:
        logging.debug(e)
        return {"error": "There was an error when creating the instance."}, 500
    except Exception as e:
        logging.debug(e)
        return {"error": "There was an error when processing the request."}, 500
    
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

    return jsonify(vm.getInstanceMetadata(user, vm_id))

@app.route('/v1/vm/modify/<vm_id>', methods=['POST'])
@jwt_required
def api_vm_modification(vm_id=None):
    user = return_calling_user()
    if not vm_id:
        return {"error": "VM ID must be provided."}, 400
    return jsonify(vm.getInstanceMetadata(user, vm_id))


@app.route('/v1/vm/instance_types/describe/all', methods=['GET'])
def api_instance_types_describe_all():
    inst = Instance()
    instance_types = inst.get_all_instance_configurations()
    
    return jsonify(vm.getInstanceMetadata(user, vm_id))

####################
# Namespace: vm 
# Component: images
# vm/images

@app.route('/v1/vm/images/guest/describe-all', methods=['GET'])
def api_guest_image_all():
    manager = ImageManager()
    images = manager.getAllImages("guest")
    imgs = []
    for image in images:
        imgs.append({
            "created": image.created,
            "guest_image_id": image.guest_image_id,
            "name": image.name,
            "description": image.description,
            "minimum_requirements": image.minimum_requirements,
            "guest_image_metadata": image.guest_image_metadata,
            "tags": image.tags
        })
    return jsonify(imgs)

@app.route('/v1/vm/images/guest/describe/<img_id>', methods=['GET'])
def api_guest_image_describe(img_id=None):
    if not img_id:
        return {"error": "Image Id must be provided."}, 400
    
    manager = ImageManager()

    try: 
        image = manager.getImage("guest", img_id)
    except InvalidImageId as e:
        return {"error": "Image Id does not exist."}, 404
    
    imgs = []
    imgs.append({
        "created": image.created,
        "guest_image_id": image.guest_image_id,
        "name": image.name,
        "description": image.description,
        "minimum_requirements": image.minimum_requirements,
        "guest_image_metadata": image.guest_image_metadata,
        "tags": image.tags
    })

    return jsonify(imgs)

@app.route('/v1/vm/images/guest/register', methods=['POST'])
@jwt_required
def api_guest_image_register():
    user = return_calling_user()
    manager = ImageManager()

    if not "ImagePath" in request.args:
        return {"error": "ImagePath must be provided when registering a guest image."}, 400
    
    if not "ImageName" in request.args:
        return {"error": "ImageName must be provided when registering a guest image."}, 400 
    
    if not "ImageDescription" in request.args:
        return {"error": "ImageDescription must be provided when registering a guest image."}, 400 

    try: 
        img_id = manager.registerImage(
            "guest",
            request.args["ImagePath"], 
            request.args["ImageName"], 
            request.args["ImageDescription"],
            request.args["ImageUser"] if "ImageUser" in request.args else "",
            user,
            host=None,
            tags=request.args["Tags"] if "Tags" in request.args else {},
        )
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
    keystore = KeyStore()
    keys = keystore.get_all(user)
    k = []
    for key in keys:
        k.append({
            "fingerprint": key.fingerprint,
            "key_id": key.key_id,
            "key_name": key.key_name,
        })
    
    return jsonify(k)

@app.route('/v1/vm/ssh_key/describe/<ssh_key_name>', methods=['GET'])
@jwt_required
def api_ssh_key(ssh_key_name=None):
    user = return_calling_user()
    try:
        key = KeyStore().get(user, ssh_key_name)
    except KeyDoesNotExist:
        return {"error": "KeyName does not exist."}, 404
    
    resp = [{
        "fingerprint": key.fingerprint,
        "key_id": key.key_id,
        "key_name": key.key_name,
    }]

    return jsonify(resp)

@app.route('/v1/vm/ssh_key/create', methods=['POST'])
@jwt_required
def api_ssh_key_create():
    user = return_calling_user()

    if not "KeyName" in request.args:
        return {"error": "KeyName must be provided when creating an ssh key."}, 400

    try:
        result = KeyStore.create_key(user, request.args["KeyName"])
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
        key = KeyStore().get(user, ssh_key_name)
    except KeyDoesNotExist:
        return {"error": "Key (KeyName) with that name does not exist."}, 404
    
    key.delete()

    return jsonify({"result": "ok"})

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
        results = KeyStore.store_key(user, request.args["KeyName"], pub_key)
    except KeyNameAlreadyExists:
        return {"error": "Key (KeyName) with that name already exists."}, 400
    except PublicKeyAlreadyExists:
        return {"error": "Public Key (PublicKey) with that fingerprint already exists."}, 400

    return jsonify(results)

####################
# Namespace: access 
# access/

@app.route('/v1/access/describe/all', methods=['GET'])
@jwt_required
def api_access_describe_all_users():
    user = return_calling_user()

    usermanager = UserManager()
    users = usermanager.get_all_users(user.account)
    resp = []
    for usr in users:
        resp.append({
            "user_id": usr.user_id,
            "username": usr.username,
            "name": usr.name,
            "created": usr.created,
            "active": usr.active,
            "tags": usr.tags
        })
    
    return jsonify(resp)


@app.route('/v1/access/describe/caller', methods=['GET'])
@jwt_optional
def api_access_describe_caller():
    user = return_calling_user()

    usermanager = UserManager()

    alias_details = {}
    if user.primary is False:
        uid = user.related
        alias_details = {
            "alias_auth_id": user.auth_id,
            "created": user.created,
            "tags": user.tags,
        }
    else:
        uid = user.user_id

    usr = usermanager.get_user(uid)
    resp = []
    resp.append({
        "user_id": usr.user_id,
        "username": usr.username,
        "name": usr.name,
        "created": usr.created,
        "active": usr.active,
        "alias": alias_details,
        "tags": usr.tags,
    })
    
    return jsonify(resp)

@app.route('/v1/access/describe/<user_id>', methods=['GET'])
@jwt_required
def api_access_describe_user(user_id):
    user = return_calling_user()

    usermanager = UserManager()
    usr = usermanager.get_user(user_id)
    resp = []
    resp.append({
        "user_id": usr.user_id,
        "username": usr.username,
        "name": usr.name,
        "created": usr.created,
        "active": usr.active,
        "tags": usr.tags
    })
    
    return jsonify(resp)

@app.route('/v1/access/create', methods=['POST'])
@jwt_required
def api_access_create_user():
    user = return_calling_user()

    if "Username" not in request.args:
        return {"error": "Username must be provided when creating a new user."}, 400

    if "Name" not in request.args:
        return {"error": "Name must be provided when creating a new user."}, 400
    
    tags = unpack_tags(request.args)

    usermanager = UserManager()
    new_user = usermanager.create_user(
        user.account, 
        request.args["Username"], 
        request.args["Name"],
        tags,
        request.args["Password"] if "Password" in request.args else None
    )

    return jsonify(new_user)

@app.route('/v1/access/delete/<user_id>', methods=['POST'])
@jwt_required
def api_access_terminate_user():
    user = return_calling_user()

    if "Username" not in request.args:
        return {"error": "Username must be provided when creating a new user."}, 400

    if "Name" not in request.args:
        return {"error": "Name must be provided when creating a new user."}, 400
    
    tags = unpack_tags(request.args)

    usermanager = UserManager()
    new_user = usermanager.create_user(
        user.account, 
        request.args["Username"], 
        request.args["Name"],
        tags,
        request.args["Password"] if "Password" in request.args else None
    )

    return jsonify(new_user)

####################
# Namespace: network 
# network/
@app.route('/v1/network/describe/all', methods=['GET'])
@jwt_required
def api_network_describe_all():
    user = return_calling_user()

    network = VirtualNetwork()
    vnets = network.get_all_networks(user)
    response = []
    for vnet in vnets:
        response.append({
            "network_id": vnet.vnet_id,
            "name": vnet.profile_name,
            "type": vnet.type,
            "created": str(vnet.created),
            "config": vnet.config,
            "tags": vnet.tags,
        })
    
    return jsonify(response)

@app.route('/v1/network/describe/<vnet_id>', methods=['GET'])
@jwt_required
def api_network_describe_network(vnet_id=None):
    user = return_calling_user()

    network = VirtualNetwork()
    vnet = network.get_network(vnet_id, user)
    response = []
    if vnet:
        response.append({
            "network_id": vnet.vnet_id,
            "name": vnet.profile_name,
            "type": vnet.type,
            "created": str(vnet.created),
            "config": vnet.config,
            "tags": vnet.tags,
        })
    
    return jsonify(response)


@app.route('/v1/network/create', methods=['POST'])
@jwt_required
def api_network_create_network():
    user = return_calling_user()

    network = VirtualNetwork()

    for req_opt in network.create_required_options:
        if not req_opt in request.args:
            return {"error": f"{req_opt} must be provided when creating a network."}, 400
    
    if request.args["Type"] not in network.valid_network_types:
        return {"error": "Type must be one of the supported types: BridgeToLan, NAT"}, 400
    
    if request.args["Type"] == "BridgeToLan":
        request.args["Tags"] = unpack_tags(request.args)
        
        try:
            new_network = network.create(
                Name=request.args["Name"],
                User=user, 
                Type=request.args["Type"],
                **request.args
            )
        except:
            return {"error": f"Error creating network."}, 400
    
        return jsonify({"vnet_id": new_network})
    else:
        return jsonify({"error": "Other network types not currently built."})

@app.route('/v1/network/delete/<vnet_id>', methods=['POST'])
@jwt_required
def api_network_delete_network(vnet_id=None):
    user = return_calling_user()

    network = VirtualNetwork()
    vnet = network.get_network(vnet_id, user)
    response = []
    if vnet:
        vnet.delete()
    
    return jsonify(response)

####################
# Namespace: kube 
# Component: cluster
# kube/cluster

@app.route('/v1/kube/cluster/describe/all', methods=['GET'])
@jwt_required
def kube_cluster_describe_all():
    user = return_calling_user()

    kman = KubeManager()
    clusters = kman.get_all_clusters(user)
    response = []
    for cluster in clusters:
        response.append({
            "cluster_id": cluster.cluster_id,
            "created": cluster.created,
            "type": cluster.type,
            "status": {
                "status": cluster.status,
                "last_updated": cluster.last_status_update
            },
            "primary_controller": cluster.primary_controller,
            "associated_instances": cluster.assoc_instances,
            "cluster_metadata": cluster.cluster_metadata,
            "tags": cluster.tags
        })
    
    return jsonify(response)

@app.route('/v1/kube/cluster/describe/<cluster_id>', methods=['GET'])
@jwt_required
def kube_cluster_describe_cluster(cluster_id):
    user = return_calling_user()

    kman = KubeManager()
    cluster = kman.get_cluster_by_id(cluster_id, user)
    response = []
    response.append({
        "cluster_id": cluster.cluster_id,
        "created": cluster.created,
        "type": cluster.type,
        "status": {
            "status": cluster.status,
            "last_updated": cluster.last_status_update
        },
        "primary_controller": cluster.primary_controller,
        "associated_instances": cluster.assoc_instances,
        "cluster_metadata": cluster.cluster_metadata,
        "tags": cluster.tags
    })

    return jsonify(response)

@app.route('/v1/kube/cluster/create', methods=['POST'])
@jwt_required
def kube_cluster_create_cluster():
    user = return_calling_user()

    if "ImageId" not in request.args:
        return {"error": "ImageId must be provided when creating a Kubernetes cluster."}, 400
    
    if "InstanceSize" not in request.args:
        return {"error": "InstanceSize must be provided when creating a Kubernetes cluster."}, 400
    
    if "NetworkProfile" not in request.args:
        return {"error": "NetworkProfile must be provided when creating a Kubernetes cluster."}, 400
    
    vnet_obj = VirtualNetwork().get_network_by_profile_name(request.args["NetworkProfile"], user)
    if not vnet_obj:
        return {"error": "Specified NetworkProfile does not exist."}, 400
    
    iTypeSize = request.args["InstanceSize"].split(".")
    try:
        instanceDefinition = Instance(iTypeSize[0], iTypeSize[1])
    except InvalidInstanceType:
        return {"error": "Provided InstanceSize is not a valid type or size."}, 400
    
    key_name = None
    if "KeyName" in request.args:
        try:
            KeyStore().get(user, request.args["KeyName"])
            key_name = request.args["KeyName"]
        except KeyDoesNotExist:
            return {"error": "Provided KeyName does not exist."}, 400

    
    # Right now, the create kube cluster command expects these IPs to be statically defined
    # In the future, we'll look into generating these IPs ourselves if the user does not wish
    # to set the IPs.
    if "ControllerIp" not in request.args:
        return {"error": "ControllerIp must be provided when creating a Kubernetes cluster."}, 400

    ips = []
    ips.append(request.args["ControllerIp"])
    
    there_are_ips = True
    x = 1
    while there_are_ips:
        if f"Node.{x}.Ip" in request.args:
            try:
                if vnet_obj.validate_ip(request.args[f"Node.{x}.Ip"]):
                    ips.append(request.args[f"Node.{x}.Ip"])
                else:
                    return {"error": f"Provided value for Node.{x}.Ip is not a valid IP address for this network."}, 400
            except ValueError as e:
                logging.debug(e)
                return {"error": f"Provided value for Node.{x}.Ip is not valid."}, 400
        else:
            there_are_ips = False
            continue
        x += 1
    
    tags = unpack_tags(request.args)

    kman = KubeManager()
    #try:
    cluster_id = kman.create_cluster(
        user=user,
        instance_size=instanceDefinition,
        ips=ips,
        image_id=request.args["ImageId"],
        key_name=key_name,
        network_profile=request.args["NetworkProfile"],
        tags=tags,
    )
    #except:
    #    logging.debug("Encountered error when creating Kubernetes cluster")
    #    return {"error": "Server encountered an error when creating Kubernetes cluster."}, 500

    
    return jsonify({"cluster_id": cluster_id})

@app.route('/v1/kube/cluster/terminate/<cluster_id>', methods=['POST'])
@jwt_required
def kube_cluster_terminate_cluster(cluster_id):
    user = return_calling_user()

    kman = KubeManager()
    cluster = kman.get_cluster_by_id(cluster_id, user)
    if not cluster:
        return {"error": "Cluster with that cluster_id not found."}, 404
    
    kman.delete_cluster(cluster_id, user)
    
    return jsonify({"success": True})

@app.route('/v1/kube/cluster/config/<cluster_id>', methods=['GET'])
@jwt_required
def kube_cluster_get_cluster_config(cluster_id):
    user = return_calling_user()

    kman = KubeManager()
    cluster = kman.get_cluster_config(cluster_id, user)
    if not cluster:
        return {"error": "Cluster with that cluster_id not found."}, 404
    
    try:
        config = kman.get_cluster_config(cluster_id, user)
    except ClusterDoesNotExist as e:
        return {"error": "Cluster with that cluster_id not found."}, 404
    except ServerError as e:
        return {"error": e}, 500
    
    return jsonify({"kube_config": config})

####################
# Namespace: service 
# Component: msg
# service/msg

@app.route('/v1/service/msg', methods=['POST'])
@jwt_required
def service_msg():
    user = return_calling_user()

if __name__ == "__main__":
    app.run(host="0.0.0.0")
