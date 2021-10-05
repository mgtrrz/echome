import logging
import json
from .commander import BaseCommander

logger = logging.getLogger(__name__)

class QemuImg(BaseCommander):
    """
    Create a QemuImg object to pass commands to qemu-img.
    """

    base_command = '/usr/bin/qemu-img'
    
    def resize(self, filename: str, size: str):
        """Resize disk images using `qemu-img resize`.

        :param filename: Path on the local filesystem to the image file.
        :param size: Size to set for the disk image. If you specify + or -,
            it will add or remove disk space from the image. e.g. 60G, +10G

        :returns: boolean if the operation was successful.
        """
        cmds = ["resize", filename, size]
        output, return_code = self.command(cmds)
        if return_code == 0:
            return True
        else:
            return False
    
    def convert(self, filename: str, output_filename: str, output_format=None):
        """Convert or copy an image to another format using `qemu-img convert`.

        :param filename: Source filename to convert or copy.
        :param output_filename: Destination filename.
        :param output_format: Specify a format to copy to. By default, uses the
            format of the original filename. Run qemu-img -h to determine what
            formats are supported, defaults to None

        :returns: boolean if the operation was successful
        """        
        flags = []
        if output_format:
            flags.append(["-O", output_format])
        
        cmds = ["convert"] + flags + [filename, output_filename]
        output, return_code = self.command(cmds)
        if return_code == 0:
            return True
        else:
            return False
    
    def create(self, filename: str, format: str, size: str):
        """Create a new image for virtual machines using `qemu-img create`.

        :param filename: Destination filename/location for the new image.
        :param format: Image format to use. Run qemu-img -h to determine what
            formats are supported,
        :param size: Size of the image to create. Uses Qemu-img size rules:
            'k' or 'K' (kilobyte, 1024), 'M' (megabyte, 1024k), 'G' (gigabyte, 1024M),
            'T' (terabyte, 1024G), 'P' (petabyte, 1024T) and 'E' (exabyte, 1024P)  are
            supported. 'b' is ignored.

        :returns: boolean if the operation was successful
        """        
        cmds = ["create", "-f", format , filename, size]
        output, return_code = self.command(cmds)
        if return_code == 0:
            return True
        else:
            return False
        
    def info(self, filename: str):
        """Get info about an image. Returns a dictionary if the image exists.

        :param filename: Destination filename/location for the new image.

        :returns: Dictionary if successful, False if the operation was unsuccessful. 
        """
        flags = ["--output", "json"]
        
        cmds = ["info"] + [filename] + flags
        output, return_code = self.command(cmds)
        if return_code == 0:
            return json.loads(output)
        else:
            return False
