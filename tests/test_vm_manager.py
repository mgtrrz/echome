import unittest

class TestVmManager(unittest.TestCase):

    def test_generate_network_cloudinit_config(self):
        expected = """version: 2
ethernets:
  ens2:
    dhcp4: false
    dhcp6: false
    addresses:
    - 172.16.9.50/24
    gateway4: 172.16.9.1
    nameservers:
      addresses:
      - 1.1.1.1
      - 1.0.0.1
"""     
        config = {
            "network_type": "BridgetoLan",
            "private_ip": "172.16.9.50/24",
            "gateway_ip": "172.16.9.1"
        }
        m = vm_manager.vmManager()
        actual = m._VmManager__generate_cloudinit_config(config)
        self.assertEqual(expected, actual)

if __name__ == '__main__':
    unittest.main()
