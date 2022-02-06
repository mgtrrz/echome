#!/bin/bash
set -e

echo "[>] Starting Kubernetes image preparation!"

echo "[*] Preparing variables.."

apt update && apt upgrade -y
apt install curl jq -y

server_file="/root/server_info.yaml"
echome_url=$(jq -r '.server_addr + .endpoint' < $server_file )
echome_token=$(jq -r '.auth_token' < $server_file )

function cleanup() {
    echo "[*] Deleting files"
    find /root/ -maxdepth 1 -not -path '*/.*' -type f -print -delete
}

function script_failure() {
    echo "[!] CAUGHT SIGINT OR ERR: CLEANING UP"
    auth_header="Authorization: Bearer ${echome_token}"
    curl -s -X POST -d "Success=false&Self=$(cat /var/lib/cloud/data/instance-id)&ErrorLog=$(tail -n25 /var/log/cloud-init-output.log)" \
        -H 'Accept: application/json'  -H "${auth_header}" "${echome_url}" 

    # Finally cleanup
    cleanup
}

trap script_failure SIGINT ERR

echo "[*] Installing requirements.."

apt install ebtables ethtool apt-transport-https nfs-common containerd -y

echo "[*] Preparing container environment.."

modprobe overlay
modprobe br_netfilter
cat <<EOF | tee /etc/modules-load.d/containerd.conf
overlay
br_netfilter
EOF

cat <<EOF | tee /etc/sysctl.d/99-kubernetes-cri.conf
net.bridge.bridge-nf-call-iptables  = 1
net.ipv4.ip_forward                 = 1
net.bridge.bridge-nf-call-ip6tables = 1
EOF

sysctl --system

# containerd
mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml

sed -i 's/SystemdCgroup = false/SystemdCgroup = true/g' /etc/containerd/config.toml

systemctl restart containerd

# Installing Kubeadm

echo "[*] Installing Kubeadm.."

KUBE_VERSION=$(cat /root/kube_version)

curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
cat <<EOF >/etc/apt/sources.list.d/kubernetes.list
deb http://apt.kubernetes.io/ kubernetes-xenial main
EOF

apt update

# Pin kubeadm, kubelet, kubectl to specific versions for this image
apt install -y kubelet="${KUBE_VERSION}*" kubeadm="${KUBE_VERSION}*" kubectl="${KUBE_VERSION}*"

apt-mark hold kubelet="${KUBE_VERSION}*" kubeadm="${KUBE_VERSION}*" kubectl="${KUBE_VERSION}*"

# Preload images:
kubeadm config images pull

cleanup

echo "[*] Posting to ecHome.."
# Upload data to echome
auth_header="Authorization: Bearer ${echome_token}"
curl -s -X POST -d "Success=true&Self=$(cat /var/lib/cloud/data/instance-id)" -H 'Accept: application/json'  -H "${auth_header}" "${echome_url}" 

echo "[*] Complete"
