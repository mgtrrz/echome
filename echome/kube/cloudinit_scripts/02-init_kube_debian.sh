#!/bin/bash
set -e

apt update && apt upgrade -y

apt install python3-pip -y
pip install j2cli

vault_token=$(grep "vault_token" /root/vars | awk -F'=' '{print $2}')
vault_addr=$(grep "vault_addr" /root/vars | awk -F'=' '{print $2}')
vault_path=$(grep "vault_path" /root/vars | awk -F'=' '{print $2}')

# Generate the kubeadm config file
KUBEADM_TOKEN=$(kubeadm token generate)
HOSTNAME=$(cat /etc/hostname)
export KUBEADM_TOKEN
export HOSTNAME
j2 -f yaml /root/kubeadm_template.yaml /root/cluster_info.yaml -o /root/kube_init.yaml

# Init the cluster, skipping certs
kubeadm init --config /root/kube_init.yaml

# Upload data to Vault
curl -s -X POST --data @payload.json --header "X-Vault-Token: ${vault_token}" "${vault_addr}/v1/${vault_path}/admin" 

rm /root/vars
