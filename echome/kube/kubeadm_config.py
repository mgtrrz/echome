from audioop import add
import logging
import sys
import yaml
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List


logger = logging.getLogger(__name__)

@dataclass
class KubeadmConfig(ABC):

    version: str

    def get_api_version(self):
        ns = "kubeadm.k8s.io"
        if self.version == "1.23":
            return f"{ns}/v1beta2"
        elif self.version == "1.22":
            return f"{ns}/v1beta2"
        elif self.version == "1.21":
            return f"{ns}/v1beta2"
        elif self.version == "1.20":
            return f"{ns}/v1beta2"
        elif self.version == "1.19":
            return f"{ns}/v1beta2"
    
    def get_manifest_headers(self, kind:str = "") -> dict:
        return {
            'apiVersion': self.get_api_version(),
            'kind': kind
        }
    
    @abstractmethod
    def generate_document(self) -> dict:
        """Generate the document. This function returns a Python dictionary with all of the
        Kubeadm options defined. Use generate_yaml() to generate the YAML from the dict"""
    

    def generate_yaml(self, additional_documents:List[dict] = None):
        """Returns a YAML document generated from the Kubeadm dataclass. Additional documents
        can be provided in the additional_documents list and this function will neatly separate
        them with triple dashes
        ---
        """
        if additional_documents is None:
            additional_documents = []
        return self._yaml_dump([self.generate_document()] + additional_documents)


    def _yaml_dump(self, contents:List):
        return yaml.safe_dump_all(contents, sort_keys=False, default_flow_style=False)
    


@dataclass
class KubeadmJoinConfig(KubeadmConfig):
    """Creates the Kubeadm Join configuration file that will be used by Kubeadm
    to join existing Kubernetes clusters"""
    controller_address: str
    token: str
    ca_cert_hashes: str
    timeout: str = "5m0s"

    def generate_document(self):
        config = self.get_manifest_headers('JoinConfiguration')

        config['discovery'] = {
            'bootstrapToken': {
                'apiServerEndpoint': self.controller_address,
                'token': self.token,
                'unsafeSkipCAVerification': False,
                'caCertHashes': [self.ca_cert_hashes]
            },
            'timeout': self.timeout
        }

        return config


@dataclass
class KubeadmInitConfig(KubeadmConfig):
    """Creates the Kubeadm Init configuration file that will be used by Kubeadm
    to initialize the cluster. This is combined with KubeadmClusterConfig."""
    kubeadm_token: str
    controller_ip: str
    hostname: str
    token_ttl: str = "0"


    def generate_document(self):
        config = self.get_manifest_headers('InitConfiguration')

        config['bootstrapTokens'] = [
            {
                'groups': [
                    'system:bootstrappers:kubeadm:default-node-token'
                ],
                'token': self.kubeadm_token,
                'ttl': self.token_ttl,
                'usages': [
                    'signing',
                    'authentication'
                ]
            }
        ]

        config['localAPIEndpoint'] = {
            'advertiseAddress': self.controller_ip,
            'bindPort': 6443
        }

        config['nodeRegistration'] = {
            'imagePullPolicy': 'IfNotPresent',
            'name': self.hostname,
            'taints': None
        }
        
        return config


@dataclass
class KubeadmClusterConfig(KubeadmConfig):
    """Creates the Kubeadm Init configuration file that will be used by Kubeadm
    to configure details about the Kubernetes cluster. This is combined with KubeadmInitConfig"""
    cluster_name: str
    service_subnet: str = "10.96.0.0/12"
    dns_domain: str = "cluster.local"

    def generate_document(self) -> dict:
        config = self.get_manifest_headers('ClusterConfiguration')
        config['apiServer'] = {
            'timeoutForControlPlane': '4m0s'
        }
        config['clusterName'] = self.cluster_name
        config['controllerManager'] = {}
        config['dns'] = {}
        config['etcd'] = {
            'local': {
                'dataDir': '/var/lib/etcd'
            }
        }
        config['imageRepository'] = 'k8s.gcr.io'
        #config['kubernetesVersion'] = self.version
        config['networking'] = {
            'dnsDomain': self.dns_domain,
            'serviceSubnet': self.service_subnet
        }
        config['scheduler'] = {}

        return config
