import logging
from .commander import BaseCommander

logger = logging.getLogger(__name__)

class CloudLocalds(BaseCommander):
    """
    Create a disk for cloud-init to utilize nocloud
    """

    base_command = '/usr/bin/cloud-localds'
    set_verbose = True
    
    def create_image(self, user_data_file:str, output:str, meta_data_file:str = None, network_config_file:str=None,):
        """Cloud-localds

        :returns: boolean if the operation was successful.
        """
        cmds = [output, user_data_file]

        if meta_data_file:
            cmds += [meta_data_file]
        
        if network_config_file:
            cmds += [f"--network-config={network_config_file}"]

        output, return_code = self.command(cmds)
        if return_code == 0:
            return True
        else:
            return False
    
