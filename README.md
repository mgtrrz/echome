# ecHome

## About

ecHome is a home network virtualization project started in 2020 by Marcus Gutierrez. It mimics the technologies cloud providers like AWS use to rapidly provision virtual machines. ecHome is, in its current state, more of a demo than a product. It is (mostly) functional, but has always been more of an excuse to personally learn new things than to deliver a fully functional cloud. 

This project is under the MIT license, you are welcome to use my findings/code for your projects but is provided 'AS-IS'. If you would like to contribute, see the [Developing for ecHome](#developing-for-echome) section below.

## Introduction

ecHome is an easy to deploy Python docker application. It runs and manages your virtual machine's SSH keys, images, users, and more through an exposed API. It is simpler to implement and easier to learn than other existing solutions such as OpenStack.

When fully setup, you can create a virtual machine in seconds from any other computer in your home with a single command.

## Example

A user wants to set up a new virtual machine to run OpenVPN on their network. They need it to meet the following requirements:

- Ubuntu 20
- 1 core, 2 GB memory
- 30 GB disk size
- Accessible via their own SSH key

They install ecHome and then run a single command to get the virtual machine they need:

```
echome vm create --image-id gmi-492384f \
    --instance-size standard.small --network-profile home-network \
    --key my-ssh-key --disk-size 30G --name openvpn
```

## Features

* Launch a virtual machine of your flavor linux distribution in seconds.
* Launch virtual machines with IPs in your home-network that will allow them to be seen by other guests, perfect for home environments and running applications such as Pihole or Homebridge.
* Customize your own virtual machines and create images of them to later launch your prepared VM.
* Add shell scripts as user-data to your virtual machines that run on first-boot.
* Create, upload, and manage SSH keys that can be automatically imported to any linux instances that are launched.
* Launch and manage your own kubernetes clusters in a few minutes
* ecHome CLI makes it easy to manage and view several aspects of your environment from any computer within your network in the terminal.
* Use the Python SDK to manage your environment with code or use the web API to work in any other language you prefer.


## Safety

ecHome isn't designed to run in a public cloud or in a datacenter. Do not expose any ports of your ecHome installation to the outside world and only use within a home network. While ecHome requires authentication before making any changes, the safer option is to access your environment from outside by using a VPN to get into your home network. Treat any VM in your environment as you would an unauthorized computer by ensuring that all VMs and its packages are up-to-date.


## Requirements

### Server Requirements

* Virtualization enabled in the BIOS for your Intel/AMD CPU.
* Enough disk space for guest images and your virtual machines

If you're using secondary drives, mount your storage before installation and ensure that they're setup to mount automatically on boot.

### Operating System Requirements

* A clean Ubuntu 20.04 installation

The installation script will take care of installing the other required components:

* Docker
* KVM-QEMU
* Libvirt

## Installation

See the [Installation document](docs/installation/01-install.md) for steps on installing and configuring ecHome to your server.

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

## <a name="developing-for-echome"></a>Developing for ecHome

Getting started with developing ecHome is easy. Follow the [Installation document](docs/installation/01-install.md) for steps on installing and configuring ecHome to your server. In its current iteration, you can make changes to the code in a branch and use the `Make` commands for testing your changes. Run `make start` to start all the docker-compose components, then run `make dbmigrate` to prepare the database.

## Authors

* **mgtrrz** - *Initial work* - [Github](https://github.com/mgtrrz) - [Twitter](https://twitter.com/marknine)

See also the list of [contributors](https://github.com/mgtrrz/echome/contributors) who participated in this project.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
