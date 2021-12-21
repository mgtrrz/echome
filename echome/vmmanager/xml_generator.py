import xmltodict
import logging
from typing import List, Dict
from dataclasses import dataclass, field
from .models import OperatingSystem
from .models import HostMachine

logger = logging.getLogger(__name__)

@dataclass
class KvmXmlCore():
    memory: int
    cpu_count: int
    
    efi_boot: bool = False
    chipset: str = "legacy"
    os_arch: str = "x86_64"
    os_type: str = "hvm"
    bios: str = "bios"

    @property
    def machine_type(self) -> str:
        if self.chipset == "modern":
            return "q35"
        elif self.chipset == "legacy":
            return "pc"


@dataclass
class KvmXmlDisk():
    file_path: str
    alias: str
    device: str = "disk"
    driver: str = "qemu"
    type: str = "qcow2"
    target_dev: str = "vda"
    bus: str = "virtio"
    operating_system:OperatingSystem = OperatingSystem.LINUX


@dataclass
class KvmXmlRemovableMedia():
    file_path: str
    alias: str
    device: str = "cdrom"
    driver: str = "qemu"
    type: str = "raw"
    target_dev: str = "hdb"
    read_only: bool = True


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


    def __str__(self) -> str:
        return self.name


    # Return the devices to attach to the VM
    def _render_devices(self):
        # Default emulator 
        obj = {
            'emulator': '/usr/bin/kvm-spice',
            'console': {
                '@type': 'pty'
            }
        }

        # Hard Disk or removal drive devices
        devices = list(self.hard_disks.values()) + self.removable_media
        obj['disk'] = self._generate_disk_devices(devices, self.core.efi_boot)

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
            obj['graphics'] = self._generate_vnc_config()

        return obj
    

    def _generate_vnc_config(self):
        vnc_obj = {
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
            vnc_obj['@port'] = self.vnc_configuration.vnc_port
        
        return vnc_obj
    

    def _generate_disk_devices(self, devices:list, is_efi_boot:bool = False):
        rendered_devices = []
        chars = 'abcdefghijklmnop'
        iter = 0
        for dev in devices:
            if is_efi_boot:
                dev_name = f"sd{chars[iter]}"
            else:
                dev_name = dev.target_dev

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
                'alias': {
                    '@name': dev.alias
                },
                'target': {
                    '@dev': dev_name,
                    '@bus': "sata" if is_efi_boot else "ide"
                }
            }

            
            if isinstance(dev, KvmXmlRemovableMedia):
                d['readonly'] = {}
            
            rendered_devices.append(d)
            iter += 1
        
        return rendered_devices


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
        
        if self.hard_disks["vda"].operating_system == OperatingSystem.WINDOWS:
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
                        '@machine': self.core.machine_type,
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

        # readonly=‘yes’ type=‘rom’>/usr/share/edk2.git/ovmf-x64/OVMF_CODE-pure-efi.fd
        if self.core.efi_boot:
            obj['domain']['os']['loader'] = {
                '@readonly': 'yes',
                '@type': 'pflash',
                '#text': '/usr/share/OVMF/OVMF_CODE.fd', #TODO: Change this, also libvirt 6.0 has auto selecting of firmware binaries
            }


        if self.enable_smbios:
            obj['domain']['os']['smbios'] = {'@mode': 'sysinfo'}
            obj['domain']['sysinfo'] = self._render_smbios()

        return xmltodict.unparse(obj, full_document=False, pretty=True, short_empty_elements=True, indent=" ")

