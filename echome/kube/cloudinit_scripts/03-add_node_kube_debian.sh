#!/bin/bash
set -e

echo "[>] Starting add_node script"

echo "[*] Updating cluster.."

apt update && apt upgrade -y

apt install jq -y

server_file="/root/server_info.yaml"
echome_url=$(jq -r '.server_addr + .endpoint' < $server_file )
echome_token=$(jq -r '.auth_token' < $server_file )

function cleanup() {
    echo "[*] Deleting files"
    #find /root/ -maxdepth 1 -not -path '*/.*' -type f -print -delete
}

function script_failure() {
    echo "[!] CAUGHT SIGINT OR ERR: CLEANING UP"
    auth_header="Authorization: Bearer ${echome_token}"
    curl -s -X POST -d "Success=false&Self=$(cat /var/lib/cloud/data/instance-id)&ErrorLog=$(tail -n25 /var/log/cloud-init-output.log)" \
        -H 'Accept: application/json'  -H "${auth_header}" "${echome_url}" 

    # Finally cleanup
    cleanup
}

# Notify of script failure
trap script_failure SIGINT ERR

echo "[*] Joining Kubernetes cluster with Kubeadm.."

# Init the cluster
kubeadm join --config /root/node.yaml

echo "[*] Posting to ecHome.."

# Upload data to echome
auth_header="Authorization: Bearer ${echome_token}"
curl -s -X POST -d "Success=true&Self=$(cat /var/lib/cloud/data/instance-id)" -H 'Accept: application/json'  -H "${auth_header}" "${echome_url}" 

echo "[*] Complete"

cleanup
