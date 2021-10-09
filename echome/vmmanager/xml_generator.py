import libvirt
import xmltodict
import logging
from typing import List, Dict
from dataclasses import dataclass, field
from network.models import VirtualNetwork
from .models import HostMachine, Volume
from .instance_definitions import InstanceDefinition

logger = logging.getLogger(__name__)


@dataclass
class KvmXmlCore():
    memory: int
    cpu_count: int

    os_arch: str = "x86_64"
    os_type: str = "hvm"
    bios: str = "bios"


@dataclass
class KvmXmlDisk():
    file_path: str
    device: str = "disk"
    driver: str = "qemu"
    type: str = "qcow2"
    target_dev: str = "vda"
    bus: str = "virtio"
    os_type:str = "Linux"


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
class KvmXmlVncConfiguration():
    enable: bool = False
    vnc_port: str = "auto"
    vnc_password: str = ""


@dataclass
class KvmXmlObject():
    name: str
    core: KvmXmlCore
    hard_disks: Dict[str, KvmXmlDisk]
    network_interfaces: List[KvmXmlNetworkInterface] 

    # If set to True (default), we'll check the properties of the 
    # image that's set to the 1st hard disk provided
    adjust_to_os_requirements: bool = True

    removable_media: List[KvmXmlRemovableMedia] = field(default_factory=lambda: [])

    vnc_configuration: KvmXmlVncConfiguration = field(default_factory=lambda: KvmXmlVncConfiguration())


    # Linux likes utc, Windows has to have 'localtime'
    # https://libvirt.org/formatdomain.html#time-keeping
    clock_offset: str = "utc"

    host: HostMachine = field(default_factory=lambda: [])

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

        # Hard Disk or removal drive devices
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

        # Network devices
        for net_dev in self.network_interfaces:
            if net_dev.type == "bridge":
                n = {
                    '@type': net_dev.type,
                    'source': {
                        '@bridge': net_dev.source
                    }
                }
            elif net_dev.type == "nat":
                n = {
                    '@type': 'network',
                    'source': {
                        '@network': net_dev.source
                    }
                }
            obj['interface'] = n
        
        
        # VNC (If enabled)
        if self.vnc_configuration.enable:
            obj['graphics'] = {
                '@type': 'vnc',
                '@autoport': 'yes' if self.vnc_configuration.vnc_port == 'auto' else 'no',
                '@listen': '0.0.0.0',
                '@sharePolicy': 'allow-exclusive',
                '@passwd': self.vnc_configuration.vnc_password,
                'listen': {
                    '@type': 'address',
                    '@address': '0.0.0.0',
                }
            }

            if self.vnc_port != 'auto':
                obj['graphics']['@port'] = self.vnc_configuration.vnc_port


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
    

    def _render_cpu_details(self):
        return {
            '@mode': 'host-passthrough',
            '@match': 'exact',
        }
    

    def _render_features(self):
        """Enable features for the virtual machine"""
        default_features = ['acpi', 'apic']
        obj = {}

        for f in default_features:
            obj[f] = {}

        if self.additional_features:
            for f in self.additional_features:
                obj[f] = {}
        return obj


    def change_os_requirements(self):
        if not self.hard_disks:
            return
        
        if self.hard_disks[0].os_type == "Windows":
            self.clock_offset = "localtime"


    def render_xml(self) -> str:
        """Render the complete XML document """

        if self.adjust_to_os_requirements:
            self.change_os_requirements()

        obj = {
            'domain': {
                '@type': 'kvm',
                'name': self.name,
                'memory': {
                    "@unit": "MB",
                    '#text': str(self.core.memory)
                },
                'vcpu': self.core.cpu_count,
                'os': {
                    'type': {
                        # https://libvirt.org/formatcaps.html#elementGuest
                        '@arch': self.core.os_arch,
                        '#text': self.core.os_type
                    },
                    'boot': {
                        '@dev': 'hd',
                    }
                },
                'features': self._render_features(),
                'cpu': self._render_cpu_details(),
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

        return xmltodict.unparse(obj, full_document=False, pretty=True, short_empty_elements=True, indent=" ")


class VirtualMachineXmlObject:
    virtual_disk_xml_def: List[KvmXmlDisk] = []
    virtual_network_xml_def: KvmXmlNetworkInterface = None
    vnc_xml_def: KvmXmlVncConfiguration = None
    removable_media_xml_def: List[KvmXmlRemovableMedia] = []


class VirtualMachineInstance():
    
    core: KvmXmlCore
    virtual_disks: Dict[str, KvmXmlDisk] = {}
    virtual_network: KvmXmlNetworkInterface = None
    removable_media: List[KvmXmlRemovableMedia] = []
    vnc: KvmXmlVncConfiguration = None

    def __init__(self):
        self.libvirt_conn = libvirt.open('qemu:///system')


    def configure_network(self, virtual_network:VirtualNetwork):
        """Configure networking"""
        
        if virtual_network.type == VirtualNetwork.Type.BRIDGE_TO_LAN:
            type = "bridge"
            source = virtual_network.config['bridge_interface'] 
        elif virtual_network.type == VirtualNetwork.Type.NAT:
            type = "nat"
            source = virtual_network.name
            
        self.virtual_network_xml_def = KvmXmlNetworkInterface(
            type = type,
            source = source
        )
    

    def add_removable_media(self, file_path:str, target_dev:str):
        self.removable_media.append(KvmXmlRemovableMedia(
            file_path=file_path,
            target_dev=target_dev
        ))


    def add_virtual_disk(self, volume:Volume, target_dev:str):
        self.virtual_disks[target_dev] = KvmXmlDisk(
            file_path=volume.path,
            type=volume.format,
            os_type=volume.metadata["os"],
            target_dev=target_dev
        )

    
    def configure_vnc(self, vnc_port:str = None, password:str = None) -> dict:
        """Configures VNC"""
        vnc_xml_def = KvmXmlVncConfiguration(True)

        if vnc_port:
            logger.debug(f"VNC Port also specified: {vnc_port}")
            vnc_xml_def.vnc_port = vnc_port

        if password:
            vnc_xml_def.vnc_password = password

        self.vnc = vnc_xml_def
    

    def configure_core(self, instance_def:InstanceDefinition):
        self.core = KvmXmlCore(
            cpu_count=instance_def.get_cpu(),
            memory=instance_def.get_memory()
        )


    def define(self):
        xmldoc = KvmXmlObject(
            name=self.vm_db.instance_id,
            core=self.core,
            network_interfaces=[self.virtual_network],
            hard_disks=self.virtual_disks
        )

        if self.vm_xml_object.removable_media_xml_def:
            xmldoc.removable_media = self.removable_media

        # VNC
        if self.vm_xml_object.vnc_xml_def:
            xmldoc.vnc_configuration = self.vnc
        
        xmldoc.enable_smbios = False
        xmldoc.smbios_url = ""

        # Render the XML doc        
        doc = xmldoc.render_xml()

        # Create the actual XML template in the vm directory
        # We don't need to save the XML document to the file system
        # as it gets saved within libvirt itself, but this is a good
        # way to debug templates generated by our script.
        with open(f"{self.vm_dir}/vm.xml", 'w') as filehandle:
            logger.debug("Writing virtual machine XML document: vm.xml")
            filehandle.write(doc)

        logger.debug("Attempting to define XML with virsh..")
        dom = self.libvirt_conn.defineXML(doc)
        if not dom:
            raise DomainConfigurationError
        
        logger.info("Starting VM..")
        self.libvirt_conn(self.vm_db.instance_id)


class DomainConfigurationError(Exception):
    pass
