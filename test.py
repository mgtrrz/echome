import libvirt
import sys
from vm_manager import vmManager

conn = libvirt.openReadOnly(None)
if conn == None:
    print('Failed to open connection to the hypervisor')
    sys.exit(1)


domainIDs = conn.listDomainsID()
if domainIDs == None:
    print('Failed to get a list of domain IDs', file=sys.stderr)

print("Active domain IDs:")
if len(domainIDs) == 0:
    print('  None')
else:
    for domainID in domainIDs:
        print('  '+str(domainID))

conn.close()

vmHost = vmManager()
vmHost.closeConnection()