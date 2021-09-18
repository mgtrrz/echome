import logging
import subprocess
import json

logger = logging.getLogger(__name__)

class Commander():

    base_command = None

    def command(self, cmd: list):
        if self.base_command:
            cmd = [self.base_command] + cmd
        
        logger.debug("Running command: ")
        logger.debug(cmd)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
        stdout, stderr = proc.communicate()
        logger.debug(stdout.strip())

        return_code = proc.returncode
        logger.debug(f"SUBPROCESS RETURN CODE: {return_code}")
        logger.debug(stdout)
        return stdout, return_code
