import xmltodict
import logging
from typing import List
from dataclasses import dataclass, field
from network.models import VirtualNetwork
from echome.config import ecHomeConfig
from .models import HostMachine, VirtualMachine
from .instance_definitions import InstanceDefinition

logger = logging.getLogger(__name__)

@dataclass
class KvmXmlDisk():
    file_path: str
    device: str = "disk"
    driver: str = "qemu"
    type: str = "qcow2"
    target_dev: str = "vda"
    bus: str = "virtio"

@dataclass
class KvmXmlRemovableMedia():
    file_path: str
    device: str = "cdrom"
    driver: str = "qemu"
    type: str = "raw"
    target_dev: str = "hda"
    bus: str = "ide"
    read_only = True


@dataclass
class KvmXmlNetworkInterface():
    type: str
    source: str


@dataclass
class KvmXmlObject():
    name: str
    memory: int
    cpu_count: int
    host: HostMachine

    hard_disks: List[KvmXmlDisk]

    network_interfaces: List[KvmXmlNetworkInterface] 

    removable_media: List[KvmXmlRemovableMedia] = field(default_factory=lambda: [])

    os_arch: str = "x86_64"
    os_type: str = "hvm" # hvm or xen. hvm needed for windows, 
    # Linux likes utc, Windows has to have 'localtime'
    # https://libvirt.org/formatdomain.html#time-keeping
    clock_offset: str = "utc"

    additional_features: list = field(default_factory=lambda: [])
    enable_smbios: bool = False
    smbios_url:str = ""

    class Os():
        arch: str

    def __str__(self) -> str:
        return self.name

    # Return the devices to attach to the VM
    def _render_devices(self):
        obj = {
            'emulator': '/usr/bin/kvm-spice',
            'console': {
                '@type': 'pty'
            }
        }
        obj['disk'] = []

        devices = self.hard_disks + self.removable_media

        for dev in devices:
            d = {
                '@type': 'file',
                '@device': dev.device,
                'driver': {
                    '@name': dev.driver,
                    '@type': dev.type
                },
                'source': {
                    '@file': dev.file_path
                },
                'target': {
                    '@dev': dev.target_dev,
                    '@bus': dev.bus
                }
            }
            if isinstance(dev, KvmXmlRemovableMedia):
                if dev.read_only:
                    d['readonly'] = {}
            
            obj['disk'].append(d)

        for net_dev in self.network_interfaces:
            if net_dev.type == "bridge":
                n = {
                    '@type': net_dev.type,
                    'source': {
                        '@bridge': net_dev.source
                    }
                }
            obj['interface'] = n

        return obj

    # Return SMBIOS details
    def _render_smbios(self):
        return {
            '@type': 'smbios',
            'system': {
                'entry': [
                    {
                        '@name': 'manufacturer',
                        '#text': 'ecHome'
                    },
                    {
                        '@name': 'product',
                        '#text': 'Virt-Manager'
                    },
                    {
                        '@name': 'version',
                        '#text': '0.9.4'
                    },
                    {
                        '@name': 'serial',
                        '#text': f"ds=nocloud-net;s={self.smbios_url}"
                    },
                ]
            }
        }
    
    def _render_cpu_details(self, host:HostMachine):
        return {
            '@mode': 'host-passthrough',
            '@match': 'exact',
            #'model': 'EPYC'
        }
    
    # Enable features for the virtual machine
    def _render_features(self):
        default_features = ['acpi', 'apic']
        obj = {}

        for f in default_features:
            obj[f] = {}

        if self.additional_features:
            for f in self.additional_features:
                obj[f] = {}
        return obj

    # Render the complete XML document 
    def render_xml(self, host:HostMachine):
        obj = {
            'domain': {
                '@type': 'kvm',
                'name': self.name,
                'memory': {
                    "@unit": "MB",
                    '#text': str(self.memory)
                },
                'vcpu': self.cpu_count,
                'os': {
                    'type': {
                        # https://libvirt.org/formatcaps.html#elementGuest
                        '@arch': self.os_arch,
                        '#text': self.os_type
                    },
                    'boot': {
                        '@dev': 'hd',
                    }
                },
                'features': self._render_features(),
                'cpu': self._render_cpu_details(host),
                'clock': {
                    '@offset': self.clock_offset,
                    'timer': [
                        {
                            '@name': 'rtc',
                            '@tickpolicy': 'catchup'
                        },
                        {
                            '@name': 'pit',
                            '@tickpolicy': 'delay'
                        },
                        {
                            '@name': 'hpet',
                            '@present': 'no'
                        }
                    ]
                },
                'devices': self._render_devices()
            }
        }

        if self.enable_smbios:
            obj['domain']['os']['smbios'] = {'@mode': 'sysinfo'}
            obj['domain']['sysinfo'] = self._render_smbios()

        return xmltodict.unparse(obj, full_document=False, pretty=True, short_empty_elements=True)

class XmlGenerator():
    @staticmethod
    def generate_template(vm_id:str, vnet:VirtualNetwork, instance_type:InstanceDefinition, image_path:str, cloudinit_iso_path:str = None):
        """Generates the XML template for use with defining in libvirt.

        :param vm_id: Virtual Machine Id
        :type vm_id: str
        :param vnet: Virtual Network object for determining if a bridge interface should be used.
        :type vnet: VirtualNetwork
        :key instance_type: Instance type for this VM
        :type instance_type: Instance
        :key image_path: Path to the root virtual disk for the virtual machine.
        :type image_path: str
        :key cloudinit_iso_path: Path to the location of the cloudinit iso for this virtual machine, defaults to None. 
            If attached, the XML document will add a virtual disk with a mount to the cloudinit iso. 
        :type cloudinit_iso_path: str
        :return: XML document as a string
        :rtype: str
        """        

        enable_smbios = False
        metadata_api_url = ""
        network = []
        removable_media = []

        if cloudinit_iso_path:
            removable_media.append(KvmXmlRemovableMedia(cloudinit_iso_path))

        if vnet.type == VirtualNetwork.Type.BRIDGE_TO_LAN:
            # If it is BridgeToLan, we need to add the appropriate bridge interface into the XML
            # template
            network.append(KvmXmlNetworkInterface(
                type = "bridge",
                source = vnet.config['bridge_interface']
            ))
        else:
            # If the new VM is not using the BridgeToLan network type, add smbios
            # information for it to use the metadata service.
            ech = ecHomeConfig.EcHome()
            metadata_api_url = f"{ech.metadata_api_url}:{ech.metadata_api_port}/{vm_id}/"
            logger.debug(f"Generated Metadata API url: {metadata_api_url}")
            enable_smbios = True
        
        xmldoc = KvmXmlObject(
            name=vm_id,
            memory=instance_type.get_memory(),
            cpu_count=instance_type.get_cpu(),
            hard_disks=[
                KvmXmlDisk(image_path)
            ],
            network_interfaces=network,
            removable_media=removable_media,
            enable_smbios=enable_smbios,
            smbios_url=metadata_api_url
        )
        
        return xmldoc.render_xml()