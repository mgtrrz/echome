#!/bin/bash
set -e

echo "[>] Starting Kubernetes init!"

echo "[*] Installing dependencies.."

apt update && apt upgrade -y

apt install jq -y

server_file="/root/server_info.yaml"
echome_url=$(jq -r '.server_addr + .endpoint' < $server_file )
echome_token=$(jq -r '.auth_token' < $server_file )

function cleanup() {
    echo "[*] Deleting files"
    find /root/ -maxdepth 1 -not -path '*/.*' -type f -print -delete
}

function script_failure() {
    echo "[!] CAUGHT SIGINT OR ERR: CLEANING UP"
    jq -n '{data: $ARGS.named}' \
        --arg Success "false" \
        --arg ErrorLog "$(tail -n25 /var/log/cloud-init-output.log)" > /root/script_fail.json
    
    auth_header="Authorization: Bearer ${echome_token}"
    curl -s -X POST --data @/root/script_fail.json -H 'Accept: application/json'  -H "${auth_header}" "${echome_url}" 

    # Finally cleanup
    cleanup
}

# Notify of script failure
trap script_failure SIGINT ERR

echo "[*] Initializing Kubernetes with Kubeadm.."

# Init the cluster
kubeadm init --config /root/kube_init.yaml

echo "[*] Configuring Kubernetes networking.."

# Install Calico networking
# In the future, we can choose different network options
curl https://docs.projectcalico.org/manifests/calico.yaml -O
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl apply -f calico.yaml

echo "[*] Gathering data.."

# Generate sha from certs
ca_sha_value=$(openssl x509 -pubkey -in /etc/kubernetes/pki/ca.crt | openssl rsa -pubin -outform der 2>/dev/null | openssl dgst -sha256 -hex | sed 's/^.* /sha256:/')

# Create JSON file with kube data
jq -n '{data: $ARGS.named}' \
    --arg Success "true" \
    --arg CaSha "${ca_sha_value}"  \
    --arg AdminConf "$(cat /etc/kubernetes/admin.conf)" > /root/payload.json

echo "[*] Posting to ecHome.."

# Upload data to echome
auth_header="Authorization: Bearer ${echome_token}"
curl -s -X POST --data @/root/payload.json -H 'Accept: application/json'  -H "${auth_header}" "${echome_url}" 

echo "[*] Complete"

cleanup
