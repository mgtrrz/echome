import xmltodict
from typing import List
from dataclasses import dataclass, field


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
    
    def get_name(self):
        return {"name": self.name}

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
    def render_xml(self):
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
                'cpu': {
                    '@mode': 'custom',
                    '@match': 'exact',
                    'model': 'EPYC'
                },
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

# myobj = KvmXmlObject(
#     name="testing!",
#     memory=4096,
#     cpu_count=2,
#     hard_disks=[
#         KvmXmlDisk("/test/hello/something.qcow2")
#     ],
#     network_interfaces=[KvmXmlNetworkInterface(
#         type="bridge",
#         source="br0"
#     )],
#     removable_media=[
#         KvmXmlRemovableMedia("/cdrom")
#     ],
#     enable_smbios=True
# )
# print(myobj.render_xml())