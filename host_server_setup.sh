#!/bin/bash

echo "ecHome Host Server Setup\n"

gitmethod = $1

echo "The script is designed to pull ecHome from the git repo for development."
echo "git clone depends on having this server's ssh key added to your Github repo."
echo "Otherwise, clone via http will work without needing to configure anything."
read -p "Clone via http?" -n 1 -r
echo    # (optional) move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    exit 1
fi

# Script designed for:
# Ubuntu 18.04.4 LTS
sudo apt install -y qemu-kvm libvirt-bin libvirt-dev virtinst bridge-utils cpu-checker libguestfs-tools jq ovmf pkg-config bridge-utils cloud-image-utils
sudo apt install -y postgresql postgresql-contrib postgresql-server-dev-10
sudo apt install -y python3-pip virtualenv

# This application to be installed in:
# /opt/echome/

sudo useradd -m -d /opt/echome -G lxd,kvm,libvirt,sudo echome
#sudo usermod -s /usr/sbin/nologin echome

echo '# User rules for echome' | sudo tee -a /etc/sudoers.d/echome
echo 'echome ALL=(ALL) NOPASSWD:ALL' | sudo tee -a /etc/sudoers.d/echome

# Determine if host is ready for virtualization
sudo virt-host-validate qemu
sudo virt-host-validate lxc

# Development specific steps:
cd ~
git clone git@github.com:mgtrrz/echome.git
cd echome/
echome_dir=$(pwd)

sudo -u echome -H bash -c "cd /opt/echome; ln -s ${echome_dir}/echome ./app"

# Add the echome user and your user to the Developers group to allow access to the echome app directory
sudo groupadd Developers 
sudo usermod -a -G Developers echome
sudo usermod -a -G Developers ${USER}
sudo chgrp -R Developers ${echome_dir}/echome

# Database/config files for echome
sudo mkdir -pv /etc/echome/
sudo cp ${echome_dir}/database.ini.template /etc/echome/database.ini
sudo cp ${echome_dir}/echome.ini.template /etc/echome/echome.ini
sudo chown -R echome. /etc/echome

psqlpass=$(openssl rand -base64 20)

# Create PSQL user for echome
sudo -u postgres bash -c "psql -c \"CREATE USER echome WITH PASSWORD '${psqlpass}';\""
sudo -u postgres bash -c "psql -c \"CREATE DATABASE echome;\""
sudo -u postgres bash -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE echome to echome;\""

sudo -u echome bash -c "echo \"[database]\" > /etc/echome/database.ini; echo \"db.url=postgresql://echome:${psqlpass}@localhost/echome\" >> /etc/echome/database.ini " 

echo "Done! 

Setup a bridge network on your ubuntu server with the name 'br0'. Example guide here:
https://fabianlee.org/2019/04/01/kvm-creating-a-bridged-network-with-netplan-on-ubuntu-bionic/

Set up two new directories for guest images and user accounts. These can be defined anywhere but must be accessible and writable to the echome user.
Once these directories are created, edit /etc/echome/echome.ini and specify the directories in there.

Perform the following steps to make sure the echome app works as expected:
$ sudo su echome
$ cd ~/app/
$ virtualenv -p python3 venv
$ source venv/bin/activate
$ python api.py
 * Serving Flask app "api" (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.

If all is well, you should see Flask start in development server and start serving requests at port 5000.
"