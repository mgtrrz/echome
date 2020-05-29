# Determine if host is ready for virtualization
virt-host-validate qemu
virt-host-validate lxc

# Ubuntu 18.04.4 LTS
sudo apt install libguestfs-tools jq

# This application to be installed in:
/opt/echome/


# https://mathiashueber.com/configuring-hugepages-use-virtual-machine/
# for Windows VMs
# If error, install
hugeadm --explain
sudo apt install hugepages
# follow the article to configure, add to your Xml:
  <currentMemory unit='MB'>$VM_MEMORY</currentMemory>
  <memoryBacking>    
    <hugepages/>  
  </memoryBacking>
  <vcpu>$VM_CPU_COUNT</vcpu>