class VirtualMachineDoesNotExist(Exception):
    pass

class VirtualMachineTerminationException(Exception):
    pass

class VirtualMachineConfigurationError(Exception):
    pass

class InvalidLaunchConfiguration(Exception):
    pass

class LaunchError(Exception):
    pass
