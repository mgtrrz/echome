#!/bin/bash

echo "ecHome Host Server Setup\n\n"

echo "Use 'http' or 'ssh' to git clone the echome repository?"
echo "Defaults to 'http' on key press enter. Fastest, no ssh key setup necessary."
echo "ssh option requires creating ssh key and importing it to your Github profile."
read -p "Type: http -or- ssh [http] " -r
if [[ $REPLY =~ "http" || $REPLY == "" ]]
then
  git_url="https://github.com/mgtrrz/echome.git"
elif [[ $REPLY =~ "ssh" ]]
then
  git_url="git@github.com:mgtrrz/echome.git"
else
  echo "Unrecognized option!"
  exit 1
fi

# Script designed for:
# Ubuntu 18.04.4 LTS
echo ": Updating/upgrading packages"
sudo apt update && sudo apt upgrade -y

echo ": Installing packages"
#sudo apt install -y qemu-kvm libvirt-bin libvirt-dev virtinst bridge-utils cpu-checker libguestfs-tools jq ovmf pkg-config bridge-utils cloud-image-utils
#sudo apt install -y postgresql postgresql-contrib postgresql-server-dev-10
#sudo apt install -y python3-pip virtualenv nginx

sudo apt install -y qemu-kvm bridge-utils openvswitch-switch


# Determine if host is ready for virtualization
# sudo virt-host-validate qemu
# sudo virt-host-validate lxc

# Development specific steps:

# Database/config files for echome
echo ": Moving configuration files into place."
sudo mkdir -pv /etc/echome/
sudo cp ./echome.ini.template /etc/echome/echome.ini

echo "Done! 

Setup a bridge network on your ubuntu server with the name 'br0'. Example guide here:
https://fabianlee.org/2019/04/01/kvm-creating-a-bridged-network-with-netplan-on-ubuntu-bionic/

Set up two new directories for guest images and user accounts. These can be defined anywhere but must be accessible and writable to the echome user.
Once these directories are created, edit /etc/echome/echome.ini and specify the directories in there.

For working in a Development environment (recommended if making changes to code):

Perform the following steps to make sure the echome app works as expected:
$ sudo su echome
$ cd ~/app/
$ source venv/bin/activate
$ python api.py
 * Serving Flask app 'api' (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.

If all is well, you should see Flask start in development server and start serving requests at port 5000. The Flask development web server
will automatically reload on file changes.
"
