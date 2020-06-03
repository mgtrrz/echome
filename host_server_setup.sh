
# Ubuntu 18.04.4 LTS
sudo apt-get install qemu-kvm libvirt-bin virtinst bridge-utils cpu-checker 
sudo apt install libguestfs-tools jq ovmf

# Determine if host is ready for virtualization
virt-host-validate qemu
virt-host-validate lxc

# This application to be installed in:
# /opt/echome/

sudo useradd -m -d /opt/echome -G lxd,kvm,libvirt,sudo echome
usermod -s /usr/sbin/nologin echome

echo '# User rules for echome' >> /etc/sudoers.d/echome
echo 'echome ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers.d/echome

sudo pip3 install pipenv