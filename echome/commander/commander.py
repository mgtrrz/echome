import logging
import subprocess

logger = logging.getLogger(__name__)

class BaseCommander():

    base_command = ""
    set_verbose = False
    verbose_flag = ["-v"]
    env = {}

    def command(self, cmd: list, wait: bool = True):
        """Run a command."""

        opt_verbose = self.verbose_flag if self.set_verbose else ""
        cmd = [self.base_command] + opt_verbose + cmd
        
        logger.debug(f"Running command: {cmd}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True, env=self.env)
        if wait:
            logger.debug("wait set to True. Waiting..")
            proc.wait()
            logger.debug("Process Wait finished")
        stdout, stderr = proc.communicate()
        logger.debug(stdout)
        logger.debug(f"SUBPROCESS RETURN CODE: {proc.returncode}")

        if proc.returncode != 0:
            if stderr:
                logger.error(f"stderr: {stderr}")

        return stdout, proc.returncode


class CommandExitedWithError(Exception):
    pass
