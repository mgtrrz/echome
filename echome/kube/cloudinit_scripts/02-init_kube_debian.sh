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

# Init the cluster
kubeadm init --config /root/kube_init.yaml

# Generate sha from certs
ca_sha=$(openssl x509 -pubkey -in /etc/kubernetes/pki/ca.crt | openssl rsa -pubin -outform der 2>/dev/null | openssl dgst -sha256 -hex | sed 's/^.* /sha256:/')



# Upload data to Vault
curl -s -X POST --data @payload.json --header "X-Vault-Token: ${vault_token}" "${vault_addr}/v1/${vault_path}/admin" 

rm /root/vars
