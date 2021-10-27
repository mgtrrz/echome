# ecHome

Deploy cloud images to your local home network for ultra fast provisioning of linux instances. ECHome allows you to bring some of the convenient cloud features such as cloud-init user-data scripts on boot, SSH key insertion, VM snapshots and image creation.

ecHome is an easy to deploy python docker application designed to run and manage virtual machines while exposing an HTTP API that allows management of various aspects of ecHome. It's responsible for managing virtual machines, ssh keys, images, users, and more while being easier to implement in a home-lab environment and easier to learn than more complicated cloud infrastructure alternatives such as OpenStack.

When fully setup, you can create a virtual machine in seconds from any other computer in your home with a simple command:

```
echome vm create --image-id gmi-492384f --instance-size standard.small --network-profile home-network --key my-ssh-key --disk-size 30G --name openvpn
```

This is a currently a work-in-progress and API endpoints may change with any release.

If there's any issues, bugs, or features you'd like to see, please use the Issues tab above.

## Requirements

### Application Requirements

* A clean Ubuntu 18.04 installation
* Docker
* QEMU 2.11

A Note on the QEMU version: QEMU is up to version 5, however, Ubuntu 18.04's APT repository only has version 2.11. In the future, we'll look into installing and utilizing more recent QEMU versions. For now, we're focusing on a lot of the base functionality.

### Server Requirements

* Virtualization enabled in the BIOS for your Intel/AMD CPU.
* Enough disk space for guest images and your virtual machines

If you're using secondary drives, mount your storage before installation and ensure that they're setup to mount automatically on boot.

## Installation

The `./host_server_setup.sh` script is currently set up to run as if you'll develop on the server, meaning it'll git clone (ssh) the echome repo and symlink some directories to `echome`'s user/app directory. In the future, installation will move files into their own places but this will work for now.

Setup a clean install of Ubuntu 18.04 on your server to start and generate an ssh key with `ssh-keygen` for your user (not root). Add your public key to your Github profile.

Grab the `host_server_setup.sh` script and run it on the machine with sudo.

```
~$ sudo apt update && sudo apt upgrade

~$ wget https://raw.githubusercontent.com/mgtrrz/echome/master/host_server_setup.sh -O host_server_setup.sh
~$ chmod +x host_server_setup.sh
~$ ./host_server_setup.sh
```

Setup a bridge network on your ubuntu server with the name 'br0'. Example guide here:
https://fabianlee.org/2019/04/01/kvm-creating-a-bridged-network-with-netplan-on-ubuntu-bionic/

Set up two new directories for guest images and user accounts. These can be defined anywhere but must be accessible and writable to the echome user.

Once these directories are created, edit /etc/echome/echome.ini and specify the directories in there.

### Post setup

Grab your cloud images and place them into your `guestimages` directory. In this example, I'm grabbing the Ubuntu 18.04 cloud image from Ubuntu's [Cloud Image directories](https://cloud-images.ubuntu.com/). Download the `amd64` architecture image, being careful to avoid `arm64`:

```
echome:/mnt/nvme/guestimages$ wget https://cloud-images.ubuntu.com/bionic/current/bionic-server-cloudimg-amd64.img

# You can confirm the image type by running qemu-img

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

ecHome is a Python django application with Postgres as the database backend and Rabbitmq as the message queuing service. At the root of the stack is the API. The API runs on the computer/host designated to run virtual machines and exposes an HTTP API that allows management of various aspects of ecHome. Its responsible for managing virtual machines, ssh keys, users, images, etc.

Documentation can be found [here](docs/web-api/01-introduction.md). Code for all of the services exists in `./echome/`

### Python-SDK

The Python SDK allows for managing aspects of ecHome by importing the library. The SDK is responsible for starting and authenticating user sessions, making the calls to the API, returning raw JSON responses, and in the future, objects based on the services.

Code for this library exists in the [echome-python-sdk repository](https://github.com/mgtrrz/echome-python-sdk). Install the library with `pip install echome-sdk`.


### CLI

The CLI interfaces allows managing ecHome from the command line. The CLI uses the Python-SDK to interact with the API. Similarly to the AWS CLI, the script works with some authentication/configuration in your user's home directory as `~/.echome/config` and `~/.echome/credentials`.

```
$ cat ~/.echome/config
[default]
server=localhost:5000
format=table
```

Code for the CLI exists in the [echome-cli repository](https://github.com/mgtrrz/echome-cli). Install it with `pip install echome-cli` and run it with `echome`.

#### Example commands

```
$ echome
usage: echome <service> <subcommand> [<args>]

The most commonly used ecHome service commands are:
   vm         Interact with ecHome virtual machines.
   sshkeys    Interact with SSH keys used for virtual machines.

$ echome vm describe-all
Name                 Vm Id        Instance Size    State    IP              Image    Created
-------------------  -----------  ---------------  -------  --------------  -------  --------------------------
ubiquiti controller  vm-a8b30fda  standard.small   running                           None
ansible_host         vm-b49c2840  standard.small   running  172.16.9.15/24           2020-05-25 03:06:22.727312
kubernetes_master    vm-29b73556  standard.medium  running  172.16.9.20/24           2020-05-27 01:11:51.596795
kubernetes_worker_1  vm-2bfecdf6  standard.medium  running  172.16.9.21/24           2020-05-27 01:12:48.866471
kubernetes_worker_2  vm-2e10d36e  standard.medium  running  172.16.9.22/24           2020-05-27 01:12:52.231098

$ echome sshkeys describe test_key --format json
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
