# Determine if host is ready for virtualization
virt-host-validate qemu
virt-host-validate lxc

# Ubuntu 18.04.4 LTS
sudo apt-get install qemu-kvm libvirt-bin virtinst bridge-utils cpu-checker 
sudo apt install libguestfs-tools jq ovmf

# This application to be installed in:
/opt/echome/
