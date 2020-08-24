#!/bin/bash
timestamp=$(date +%s)

echo "Running ecHome Kubernetes deployment"

pwd

echo "Waiting for hosts to come up.."
sleep 30

cd /ansible/playbooks/kubespray
cp -rfp inventory/sample inventory/cluster
rm -f inventory/cluster/inventory.ini inventory/cluster/group_vars/k8s-cluster/k8s-cluster.yml
cp -fp /ansible/playbooks/inventory.ini inventory/cluster/inventory.ini
cp -fp /ansible/playbooks/k8s-cluster.yml inventory/cluster/group_vars/k8s-cluster/k8s-cluster.yml

echo "Running ansible playbook.."
ansible-playbook -i inventory/cluster/inventory.ini  --become cluster.yml --private-key ./${keyname}.pem

