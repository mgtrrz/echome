#!/bin/bash

apt update && apt upgrade -y

apt install python3-pip -y
pip install j2cli

# Generate the kubeadm config file
KUBEADM_TOKEN=$(kubeadm token generate)
HOSTNAME=$(cat /etc/hostname)
export KUBEADM_TOKEN
export HOSTNAME
j2 -f yaml /root/kubeadm_template.yaml /root/cluster_info.yaml -o /root/kube_init.yaml

# Init the cluster, skipping certs
kubeadm init --config /root/kube_init.yaml
