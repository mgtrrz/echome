#!/bin/bash
set -e

echo "Installing dependencies.."

apt update && apt upgrade -y

apt install python3-pip jq -y
pip install j2cli

echo "Preparing variables.."

server_file="/root/server_info.yaml"

echome_url=$(jq -r '.server_addr + .endpoint' < $server_file )
echome_token=$(jq -r '.auth_token' < $server_file )

# Generate the kubeadm config file
KUBEADM_TOKEN=$(kubeadm token generate)
HOSTNAME=$(cat /etc/hostname)
export KUBEADM_TOKEN
export HOSTNAME

echo "Creating initial kubernetes cluster template.."

j2 -f yaml /root/kubeadm_template.yaml /root/cluster_info.yaml -o /root/kube_init.yaml

echo "Initializing Kubernetes with Kubeadm.."

# Init the cluster
kubeadm init --config /root/kube_init.yaml

echo "Configuring Kubernetes networking.."

# Install Calico networking
# In the future, we can choose different network options
curl https://docs.projectcalico.org/manifests/calico.yaml -O
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl apply -f calico.yaml

echo "Gathering data.."

# Generate sha from certs
ca_sha_value=$(openssl x509 -pubkey -in /etc/kubernetes/pki/ca.crt | openssl rsa -pubin -outform der 2>/dev/null | openssl dgst -sha256 -hex | sed 's/^.* /sha256:/')

# Create JSON file with kube data
jq -n '{data: $ARGS.named}' \
    --arg ca_sha "${ca_sha_value}"  \
    --arg kubeadm_token "${KUBEADM_TOKEN}" \
    --arg admin_conf "$(cat /etc/kubernetes/admin.conf)" > /root/payload.json

echo "Posting to ecHome.."

# Upload data to echome
auth_header="Authorization: Bearer ${echome_token}"
curl -s -X POST --data @/root/payload.json -H 'Accept: application/json'  -H "${auth_header}" "${echome_url}" 

echo "Complete"

#TODO RE-ENABLE
#rm /root/vars
