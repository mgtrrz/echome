from django.test import TestCase
from .xml_generator import (
    KvmXmlNetworkInterface,
    KvmXmlObject, 
    KvmXmlCore, 
    KvmXmlVncConfiguration,
    KvmXmlNetworkInterface,
    KvmXmlDisk,
    KvmXmlRemovableMedia
)

# Create your tests here.
class TestKvmXmlObject(TestCase):
    maxDiff = None

    def setUp(self):
        # Creating templates
        core = KvmXmlCore(
            memory="512M",
            cpu_count="1"
        )
        primary_disk = KvmXmlDisk(
            file_path="/test/directory/vm-12345678/vm-12345678.qcow2",
            alias="vol-1234567890f"
        )
        removable_media = KvmXmlRemovableMedia(
            file_path="/test/directory/iso/daft-punk-live.iso",
            alias="hda"
        )
        network = KvmXmlNetworkInterface(
            type="bridge",
            source="br0"
        )

        # Creating the Xml objects
        self.kvm_xml_object_instance = KvmXmlObject(
            name="vm-12345678",
            core=core,
            hard_disks={"vda": primary_disk},
            network_interfaces=[network],
        )
        self.kvm_xml_object_instance_with_remov_media = KvmXmlObject(
            name="vm-12345678",
            core=core,
            hard_disks={"vda": primary_disk},
            network_interfaces=[network],
            removable_media=[removable_media]
        )


    def test_render_xml(self):
        rendered_xml = '<domain type="kvm">\n <name>vm-12345678</name>\n <memory unit="MB">512M</memory>\n <vcpu>1</vcpu>\n <os>\n  <type arch="x86_64">hvm</type>\n  <boot dev="hd"/>\n </os>\n <features>\n  <acpi/>\n  <apic/>\n </features>\n <cpu mode="host-passthrough" match="exact"/>\n <clock offset="utc">\n  <timer name="rtc" tickpolicy="catchup"/>\n  <timer name="pit" tickpolicy="delay"/>\n  <timer name="hpet" present="no"/>\n </clock>\n <devices>\n  <emulator>/usr/bin/kvm-spice</emulator>\n  <console type="pty"/>\n  <disk type="file" device="disk">\n   <driver name="qemu" type="qcow2"/>\n   <source file="/test/directory/vm-12345678/vm-12345678.qcow2"/>\n   <alias name="vol-1234567890f"/>\n   <target dev="vda" bus="virtio"/>\n  </disk>\n  <interface type="bridge">\n   <source bridge="br0"/>\n  </interface>\n </devices>\n</domain>'
        self.assertEqual(self.kvm_xml_object_instance.render_xml(), rendered_xml)

        rendered_xml_with_removable_media = '<domain type="kvm">\n <name>vm-12345678</name>\n <memory unit="MB">512M</memory>\n <vcpu>1</vcpu>\n <os>\n  <type arch="x86_64">hvm</type>\n  <boot dev="hd"/>\n </os>\n <features>\n  <acpi/>\n  <apic/>\n </features>\n <cpu mode="host-passthrough" match="exact"/>\n <clock offset="utc">\n  <timer name="rtc" tickpolicy="catchup"/>\n  <timer name="pit" tickpolicy="delay"/>\n  <timer name="hpet" present="no"/>\n </clock>\n <devices>\n  <emulator>/usr/bin/kvm-spice</emulator>\n  <console type="pty"/>\n  <disk type="file" device="disk">\n   <driver name="qemu" type="qcow2"/>\n   <source file="/test/directory/vm-12345678/vm-12345678.qcow2"/>\n   <alias name="vol-1234567890f"/>\n   <target dev="vda" bus="virtio"/>\n  </disk>\n  <disk type="file" device="cdrom">\n   <driver name="qemu" type="raw"/>\n   <source file="/test/directory/iso/daft-punk-live.iso"/>\n   <alias name="hda"/>\n   <target dev="hda" bus="ide"/>\n   <readonly/>\n  </disk>\n  <interface type="bridge">\n   <source bridge="br0"/>\n  </interface>\n </devices>\n</domain>'
        self.assertEqual(self.kvm_xml_object_instance_with_remov_media.render_xml(), rendered_xml_with_removable_media)

