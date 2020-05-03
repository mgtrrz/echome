# bash script for quick provisioning of VM
# Used mainly for demonstration and understanding of how these commands work locally

name=$1
vm=$2
disk_size=$3
user="mark"
uniq_timestamp=$(date +%s)

set -e

path_to_new_vm="/data/ssd_storage/user_instances/$user/$uniq_timestamp"
mkdir -pv $path_to_new_vm

echo '''#cloud-config
chpasswd: { expire: False }
ssh_pwauth: False
hostname: test
ssh_authorized_keys:
  - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCeKJ9F5NyjxFKWBgBQFiQHofsoFi46Q2Yer0RdiuqyUusxsIzSyv+ZkWM2WuZ0V10oBC/oS0S1moVqREPUJBo5RRtwEHmTOloAy/sAMA30A58xpTbW9BjVb1Y3XxMHLnkgo5dYn1Y9P7ROrWG+sXRlfao9jYhOpEiuqif232DzSj982FVboRUO57tCAedHZFpwEUHUQDXX7hfu7x09YqHKTWW2CkH+DNwckY/90sRynY/OX9fpXLYwOgDFPP+vZas9PEGL8YNWikGyct84Dv3yYsLn9NsnleT71uXNtbE74LnvGtAUvhaKEVdO+Os5eU49pI2MDObGipQ+qpEw4zQ5 mark@Marcuss-MacBook-Pro.local
''' > $path_to_new_vm/cloudinit.yaml

echo '''version: 2
ethernets:
    ens2:
        dhcp4: false
        dhcp6: false
        addresses:
          - 172.16.9.10/24
        gateway4: 172.16.9.1
        nameservers:
          addresses:
            - 1.1.1.1
            - 1.0.0.1
''' > $path_to_new_vm/network.yaml

# Validate the cloudinit YAML file
cloud-init devel schema --config-file $path_to_new_vm/cloudinit.yaml

# Create a bootable ISO from the cloudinit file
cloud-localds -v $path_to_new_vm/cloudinit.iso $path_to_new_vm/cloudinit.yaml --network-config=$path_to_new_vm/network.yaml

# Make a copy of the "master" image
#qemu-img convert cirros-0.5.1-x86_64-disk.img new_instance/cirros-0.5.1-x86_64-disk.img
cp /data/ssd_storage/guest_images/$vm $path_to_new_vm/$vm

# Resize the image to user specified dimensions
qemu-img resize $path_to_new_vm/$vm $disk_size

chown -R libvirt-qemu. /data/ssd_storage/user_instances/

#            Using the default network: \
#            --network network=default,model=virtio \
virt-install --name $name \
            --memory 512 \
            --vcpus=1 \
            --disk $path_to_new_vm/$vm,device=disk,bus=virtio,format=qcow2 \
            --disk $path_to_new_vm/cloudinit.iso,device=cdrom \
            --os-type linux \
            --virt-type kvm \
            --graphics none \
            --network bridge:br0 \
            --import \
            --noautoconsole \
