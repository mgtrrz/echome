#!/bin/bash

apt update && apt upgrade -y

apt install python3-pip
pip install j2cli

# Generate the kubeadm config file
KUBEADM_TOKEN=$(kubeadm token generate)
export KUBEADM_TOKEN
j2 -f yaml template.yaml values.json -o kube_init.yaml

# Init the cluster, skipping certs
kubeadm init --config kube_init.yaml
