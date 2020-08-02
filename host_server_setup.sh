#!/bin/bash

echo "ecHome Host Server Setup\n\n"

echo "Use 'http' or 'ssh' to git clone the echome repository?"
echo "Defaults to 'http' on key press enter. No ssh key setup necessary."
echo "ssh option requires creating ssh key and importing to your Github profile."
read -p "Type: http -or- ssh [http] " -r
echo    # (optional) move to a new line
if [[ $REPLY =~ "http" || $REPLY == "" ]]
then
  git_url="https://github.com/mgtrrz/echome.git"
    # do dangerous stuff
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
sudo apt install -y qemu-kvm libvirt-bin libvirt-dev virtinst bridge-utils cpu-checker libguestfs-tools jq ovmf pkg-config bridge-utils cloud-image-utils
sudo apt install -y postgresql postgresql-contrib postgresql-server-dev-10
sudo apt install -y python3-pip virtualenv nginx

# This application to be installed in:
# /opt/echome/

sudo useradd -m -d /opt/echome -G lxd,kvm,libvirt,sudo echome
#sudo usermod -s /usr/sbin/nologin echome

echo '# User rules for ecHome' | sudo tee -a /etc/sudoers.d/echome
echo 'echome ALL=(ALL) NOPASSWD:ALL' | sudo tee -a /etc/sudoers.d/echome

# Determine if host is ready for virtualization
sudo virt-host-validate qemu
sudo virt-host-validate lxc

# Development specific steps:
echo ": Moving app files into place."
echo "    Cloning git directory."
cd ~
git clone ${git_url}
cd echome/
echome_dir=$(pwd)

sudo -u echome -H bash -c "cd /opt/echome; ln -s ${echome_dir}/echome ./app"

echo "    Assigning echome to developers group, correcting permissions."
# Add the echome user and your user to the Developers group to allow access to the echome app directory
sudo groupadd Developers 
sudo usermod -a -G Developers echome
sudo usermod -a -G Developers ${USER}
sudo chgrp -R Developers ${echome_dir}/echome

# Database/config files for echome
echo ": Moving database configuration files into place."
sudo mkdir -pv /etc/echome/services/
sudo cp ${echome_dir}/echome.ini.template /etc/echome/echome.ini
sudo chown -R echome. /etc/echome

# Logging in /var/log
sudo mkdir -pv /var/log/echome/
sudo chown echome. /var/log/echome/

# Create PSQL user with random password for echome
psqlpass=$(openssl rand -base64 20)

echo "    Setting up PostgreSQL user."
sudo -u postgres bash -c "psql -c \"CREATE USER echome WITH PASSWORD '${psqlpass}';\""
sudo -u postgres bash -c "psql -c \"CREATE DATABASE echome;\""
sudo -u postgres bash -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE echome to echome;\""

sudo -u echome bash -c "sed -i 's#url=PSQLADDR#url=postgresql://echome:${psqlpass}@localhost/echome#' /etc/echome/echome.ini"

echo ": Creating virtualenv for ecHome."
sudo -u echome -H bash -c "cd /opt/echome/app; virtualenv -p python3 venv;"
echo ":    Installing requirements via pip"
sudo -u echome -H bash -c "cd /opt/echome/app; source venv/bin/activate; pip install -r ./requirements.txt"

# uwsgi and nginx configuration
echo
echo ": Setting uwsgi and nginx"
sudo mkdir -pv /run/echome/
sudo chown echome. /run/echome/

echo ":   Copying services uwsgi files.."
sudo cp "${echome_dir}/system/etc/emperor.ini" /etc/echome/
sudo cp "${echome_dir}/system/etc/services/*" /etc/echome/services/

sudo cp "${echome_dir}/system/echome.service" /etc/systemd/system/

echo ":   Copying nginx files.."
sudo cp "${echome_dir}/system/nginx/echome.conf" /etc/nginx/sites-available/
sudo cp "${echome_dir}/system/nginx/echome_metadata.conf" /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/echome.conf /etc/nginx/sites-enabled
sudo ln -s /etc/nginx/sites-available/echome_metadata.conf /etc/nginx/sites-enabled
sudo unlink /etc/nginx/sites-enabled/default

sudo systemctl start echome
sudo systemctl enable echome

# Check for errors in nginx configuration files
sudo nginx -t
sudo systemctl restart nginx
cd ~


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