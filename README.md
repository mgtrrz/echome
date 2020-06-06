# ecHome

Deploy cloud images to your local home network for ultra fast provisioning of linux instances. ECHome allows you to bring some of the convenient cloud features such as cloud-init user-data scripts on boot, SSH key insertion, VM snapshots and image creation.

This is a work-in-progress and not fully installable yet from this repo. Currently, the installation steps only support Ubuntu 18.04.

There are four components to ecHome: Backend/API, Frontend/Web-Interface, Python-SDK, CLI

### Backend/API

At the root of the stack is the API runs on the computer/host designated to run virtual machines and exposes an HTTP API that allows management of various aspects of ecHome. Its responsible for managing virtual machines, ssh keys, users, images, etc.

Code for this service exists in `./echome/backend/`

#### Running the API in debug mode.

Navigate to the `./echome/` directory and run `virtualenv --python=python3.6 venv`. Activate the environment by running `source venv/bin/activate`. Install the requirements with `pip install -r ./requirements.txt`. Finally, start the API with `python api.py`.

Test connectivity by `curl`ing to your server IP address at the port listed in the `api.py` file which by default is `5000`:

```
$ curl 172.16.9.6:5000/v1/ping
{
  "response": "pong"
}
```

In ecHome's current iteration, there is no user authentication and administrator requests can be made to the server.

You can interact with the HTTP API directly to manage your ecHome host, however, it's preferred you use the Web Interface, Python-SDK (programmatic) or the CLI to do everything you need. However, an example request to create a virtual machine with the HTTP API would look like:

```
$ curl 172.16.9.6:5000/v1/vm/create\?ImageId=gmi-fc1c9a62 \
 \&InstanceSize=standard.small \
 \&NetworkType=BridgeToLan \
 \&NetworkInterfacePrivateIp=172.16.9.10\/24 \
 \&NetworkInterfaceGatewayIp=172.16.9.1 \
 \&KeyName=echome
```

### Frontend/Web-Interface

Note: Not yet implemented

Web interface that communicates to the Backend/API to manage ecHome. Javascript running on the page will be responsible for making the HTTP requests directly to the API.

Code for this service exists in `./echome/web/`

### Python-SDK

The Python SDK allows for managing aspects of ecHome by importing the library. The SDK is responsible for starting and authenticating user sessions, making the calls to the API, returning raw JSON responses, and in the future, objects based on the services.

Code for this library exists in `./python_sdk/`

#### Example code

An example for interacting with the SDK:

```
from echome import Session, Vm, Images, SshKey

import json

vm_client = Session().client("Vm")

vms = vm_client.describe_all()
print("VMs__________________________________")
for vm in vms:
    name = vm["tags"]["Name"] if "Name" in vm["tags"] else ""
    print(f"{vm['instance_id']}\t{name}")

guest_images = Session().client("Images").guest().describe_all()
print("\nGuest Images_______________________")
for guest_img in guest_images:
    print(f"{guest_img['guest_image_id']}\t{guest_img['name']}")


ssh_keys = Session().client("SshKey").describe_all()
print("\nSSH Keys___________________________")
for sshkey in ssh_keys:
    print(f"{sshkey['key_id']}\t{sshkey['key_name']}\t{sshkey['fingerprint']}")

```

```
python3 test_script.py 
VMs__________________________________
vm-a8b30fda     ubiquiti controller
vm-b49c2840     ansible_host
vm-29b73556     kubernetes_master
vm-2bfecdf6     kubernetes_worker_1
vm-2e10d36e     kubernetes_worker_2

Guest Images_______________________
gmi-d60beeba    Ubuntu 16.04 Server
gmi-fc1c9a62    Ubuntu 18.04 Server
gmi-1326e63a    Windows 10 May 2020 64-bit
gmi-6341042a    Windows Server 2020 R2 Standard Eval 64-bit

SSH Keys___________________________
key-5393842a    example_key     MD5:98:6c:0f:e5:fb:cb:74:5d:fa:f8:3c:f1:03:e3:35:5b
key-91c8cbd8    test_key        MD5:62:dd:13:e9:7f:a9:be:23:cf:df:64:ac:4b:63:77:d9
key-8ff552b8    echome  MD5:d4:d2:12:d3:95:81:9a:10:ba:43:43:15:45:08:a7:bc
```

### CLI

The CLI interfaces allows managing ecHome from the command line. The CLI uses the Python-SDK to interact with the API. Similarly to the AWS CLI, the script works with some authentication/configuration in your user's home directory as `~/.echome/config` and `~/.echome/credentials`.

```
$ cat ~/.echome/config
[default]
server=localhost:5000
format=table
```

Code for the script exists in `./cli/`

#### Example commands

```
$ echome
usage: echome <service> <subcommand> [<args>]

The most commonly used ecHome service commands are:
   vm         Interact with ecHome virtual machines.
   sshkeys    Interact with SSH keys used for virtual machines.

$ python3 main.py vm describe-all
Name                 Vm Id        Instance Size    State    IP              Image    Created
-------------------  -----------  ---------------  -------  --------------  -------  --------------------------
ubiquiti controller  vm-a8b30fda  standard.small   running                           None
ansible_host         vm-b49c2840  standard.small   running  172.16.9.15/24           2020-05-25 03:06:22.727312
kubernetes_master    vm-29b73556  standard.medium  running  172.16.9.20/24           2020-05-27 01:11:51.596795
kubernetes_worker_1  vm-2bfecdf6  standard.medium  running  172.16.9.21/24           2020-05-27 01:12:48.866471
kubernetes_worker_2  vm-2e10d36e  standard.medium  running  172.16.9.22/24           2020-05-27 01:12:52.231098

$ python3 main.py sshkeys describe test_key --format json
[
    {
        "fingerprint": "MD5:62:dd:13:e9:7f:a9:be:23:cf:df:64:ac:4b:63:77:d9",
        "key_id": "key-91c8cbd8",
        "key_name": "test_key"
    }
]
```