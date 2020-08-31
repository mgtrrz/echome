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

curl -s --header "X-Vault-Token: ${VAULT_TOKEN}" ${VAULT_ADDR}/v1/${VAULT_PATH}/data/${SSH_PRIVATE_KEY} | jq '.data.data.private_key' | awk -F\" '{print $2}' | sed 's/\\n/\n/g' > ./key.pem
chmod 400 ./key.pem

echo "Running ansible playbook.."
ansible-playbook -i inventory/cluster/inventory.ini  --become cluster.yml --private-key ./key.pem

echo "Copying kubeconfig file.."
ls -lah inventory/cluster/artifacts/
adminconf=$(cat inventory/cluster/artifacts/admin.conf)
echo -e "{\"data\": {\"admin.conf\": \"${adminconf}\"}" > payload.json
curl -s -X POST --data @payload.json --header "X-Vault-Token: ${VAULT_TOKEN}" ${VAULT_ADDR}/v1/${VAULT_PATH}/data/${SSH_PRIVATE_KEY}/admin 
