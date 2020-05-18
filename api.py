import logging
import flask
from markupsafe import escape
from flask import request, jsonify, url_for
from vm_manager import vmManager
from database import Database
from ssh_keystore import EchKeystore
from instance_definitions import Instance
from guest_image import GuestImage

app = flask.Flask(__name__)
app.config["DEBUG"] = True

user = {
    "account_id": "12345",
    "account_user_id": "11119",
}

@app.route('/', methods=['GET'])
def home():
    return {}

@app.route('/v1/vm/all', methods=['GET'])
def api_vm_all():
    vm = vmManager()
    return jsonify(vm.getAllInstances(user))

@app.route('/v1/vm/<vm_id>', methods=['GET'])
def api_vm_meta(vm_id=None):
    if not vm_id:
        return {"error": "VM ID must be provided."}, 400

    vm = vmManager()
    return jsonify(vm.getInstanceMetaData(user, vm_id))

app.run(host="0.0.0.0")