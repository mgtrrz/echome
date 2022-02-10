## ecHome Host Server Installation

The `./host_server_setup.sh` script is currently set up to run as if you'll develop on the server, meaning it'll git clone (ssh) the echome repo and symlink some directories to `echome`'s user/app directory. In the future, installation will move files into their own places but this will work for now.

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

---
Next Article: [Setup](./02-setup.md)
