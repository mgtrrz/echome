#!/bin/bash

# image prep
apt update && apt upgrade -y
apt install ebtables ethtool apt-transport-https nfs-common curl jq python3-pip -y
pip install j2cli

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
apt install containerd -y
mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml

sed -i 's/SystemdCgroup = false/SystemdCgroup = true/g' /etc/containerd/config.toml

systemctl restart containerd

# Installing Kubeadm

curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
cat <<EOF >/etc/apt/sources.list.d/kubernetes.list
deb http://apt.kubernetes.io/ kubernetes-xenial main
EOF

apt update
apt install -y kubelet kubeadm kubectl

# Preload images:
kubeadm config images pull
