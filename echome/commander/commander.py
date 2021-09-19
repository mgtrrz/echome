import logging
import subprocess

logger = logging.getLogger(__name__)

class BaseCommander():

    base_command = None
    set_verbose = False
    verbose_flag = ["-v"]

    def command(self, cmd: list):
        if self.base_command:
            if self.set_verbose:
                cmd = [self.base_command] + self.verbose_flag + cmd
            else:
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
