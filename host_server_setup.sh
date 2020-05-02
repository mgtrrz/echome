# Determine if host is ready for virtualization
virt-host-validate qemu
virt-host-validate lxc

# Ubuntu 18.04.4 LTS
sudo apt install libguestfs-tools