# ecHome

Deploy cloud images to your local home network for ultra fast provisioning of linux instances. ECHome allows you to bring some of the convenient cloud features such as cloud-init user-data scripts on boot, SSH key insertion, VM snapshots and image creation.

This is a work-in-progress and not fully installable yet from this repo. Currently, the installation steps only support Ubuntu 18.04.

Changes will be continuously pushed to **Master** until I feel that we've reached a point with features where we can put in a version number. However, if there's any objection to that, please let me know. 

If there's any issues, bugs, or features you'd like to see, please use the Issues tab above.

## Requirements

### Application requirements

* A clean Ubuntu 18.04 installation
* Python 3.6
* Postgres 11
* QEMU 2.11

A Note on the QEMU version: QEMU is up to version 5, however, Ubuntu 18.04's APT repository only has version 2.11. In the future, we'll look into installing and utilizing more recent QEMU versions. For now, we're focusing on a lot of the base functionality.


### Server requirements

* Virtualization enabled in the BIOS for your Intel/AMD CPU.
* Enough disk space for guest images and your virtual machines

In my lab/setup, I am running a Ryzen 5 1600 (6 core, 12 thread) server with 32 GB RAM. I have not yet tested this with a modern Intel processor.

## Installation

The `./host_server_setup.sh` script is currently set up to run as if you'll develop on the instance meaning it'll git clone the echome repo and symlink some directories to `echome`'s user/app directory. In the future, this is subject to change but will work for now.

Setup a clean install of Ubuntu 18.04 on your server to start and generate an ssh key with `ssh-keygen` for your user (not root). Add your public key to your Github profile.

Grab the `host_server_setup.sh` script and run it on the machine with sudo.

```
~$ wget https://raw.githubusercontent.com/mgtrrz/echome/master/host_server_setup.sh -O host_server_setup.sh
~$ chmod +x host_server_setup.sh
~$ ./host_server_setup.sh
```

Setup a bridge network on your ubuntu server with the name 'br0'. Example guide here:
https://fabianlee.org/2019/04/01/kvm-creating-a-bridged-network-with-netplan-on-ubuntu-bionic/

Set up two new directories for guest images and user accounts. These can be defined anywhere but must be accessible and writable to the echome user.
Once these directories are created, edit /etc/echome/echome.ini and specify the directories in there.

Once complete, follow the steps below in "Running the API in debug mode."

### Post setup

Grab your cloud images and place them into your `guestimages` directory. In this example, I'm grabbing the Ubuntu 18.04 cloud image from Ubuntu's [Cloud Image directories](https://cloud-images.ubuntu.com/). Download the `amd64` architecture image, being careful to avoid `arm64`:

```
echome:/mnt/nvme/guestimages$ wget https://cloud-images.ubuntu.com/bionic/current/bionic-server-cloudimg-amd64.img

# You can confirm the type of image this image is by running qemu-img

echome:/mnt/nvme/guestimages$ qemu-img info bionic-server-cloudimg-amd64.img
image: bionic-server-cloudimg-amd64.img
file format: qcow2
virtual size: 2.2G (2361393152 bytes)
disk size: 330M
cluster_size: 65536
```

qcow2 images work best for what we're doing. But any image type should work.

## Components

### Backend/API

At the root of the stack is the API. The API runs on the computer/host designated to run virtual machines and exposes an HTTP API that allows management of various aspects of ecHome. Its responsible for managing virtual machines, ssh keys, users, images, etc.

ecHome uses the `libvirt-python` library to coordinate virtual machine management with the Libvirt API. The `VmManager` class in `./echome/backend/vm_manager.py` has methods that create, terminate, and get information about a virtual machine using Libvirt.

There is not yet a web server installed or configured to serve requests to the Python API. See the section below for running the API in debug mode using Flask's built-in webserver.

Code for all of the services exists in `./echome/backend/`

#### Running the API in debug mode.

Navigate to the `./echome/` directory and run `virtualenv --python=python3.6 venv`. Activate the environment by running `source venv/bin/activate`. Install the requirements with `pip install -r ./requirements.txt`. Finally, start the API with `python api.py`.

Test connectivity by `curl`ing to your server IP address at the port listed in the `api.py` file which by default is `5000`:

```
$ curl 172.16.9.6:5000/v1/ping
{
  "response": "pong"
}
```

In ecHome's current iteration, there is no user authentication and all implemented ecHome requests can be made to the server.

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


## Authors

* **mgtrrz** - *Initial work* - [Github](https://github.com/mgtrrz) - [Twitter](https://twitter.com/marknine)

See also the list of [contributors](https://github.com/mgtrrz/echome/contributors) who participated in this project.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
