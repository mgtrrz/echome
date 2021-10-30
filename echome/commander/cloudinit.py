import logging
from .commander import BaseCommander

logger = logging.getLogger(__name__)

class CloudInit(BaseCommander):
    """
    Run Cloudinit Development tools.
    """

    base_command = '/usr/bin/cloud-init'
    
    def validate_schema(self, file_path: str):
        """Cloud-config schema validator`.

        From the docs:
        https://cloudinit.readthedocs.io/en/18.4/topics/capabilities.html#cloud-init-devel
        A #cloud-config format and schema validator. It accepts 
        a cloud-config yaml file and annotates potential schema 
        errors locally without the need for deployment. Schema 
        validation is work in progress and supports a subset of 
        cloud-config modules.

        :returns: boolean if the operation was successful.
        """
        cmds = ["devel", "schema", "--config-file", file_path]
        output, return_code = self.command(cmds)
        if return_code == 0:
            return True
        else:
            return False
    
