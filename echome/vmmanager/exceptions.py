# VmManager exceptions
class VirtualMachineDoesNotExist(Exception):
    pass

class VirtualMachineTerminationException(Exception):
    pass

class VirtualMachineConfigurationError(Exception):
    pass

class InvalidLaunchConfiguration(Exception):
    pass

class ImagePrepError(Exception):
    pass

class LaunchError(Exception):
    pass

# Image Model Exceptions
class InvalidImageId(Exception):
    pass

class InvalidImagePath(Exception):
    pass

class InvalidImageAlreadyExists(Exception):
    pass

class UserImageInvalidUser(Exception):
    pass
