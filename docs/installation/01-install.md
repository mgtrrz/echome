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
