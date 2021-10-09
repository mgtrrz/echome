import logging
import json
from .commander import BaseCommander

logger = logging.getLogger(__name__)

class VirtTools(BaseCommander):
    """ Collection of virt tools"""

    def sysprep(self, file_name: str):
        """Reset or unconfigure a virtual machine so clones can be made

        :param file_name: Path on the local filesystem to the image file.

        :returns: boolean if the operation was successful.
        """

        cmds = ['/usr/bin/virt-sysprep', '-a', file_name]
        _, return_code = self.command(cmds,)
        if return_code == 0:
            return True
        else:
            return False
    

    def sparsify(self, file_name: str):
        """Sparsify a virtual machine disk

        :param file_name: Source filename to convert or copy.

        :returns: boolean if the operation was successful
        """
        
        cmds = ['/usr/bin/virt-sparsify', '--in-place', file_name]
        output, return_code = self.command(cmds)
        if return_code == 0:
            return True
        else:
            return False
    

