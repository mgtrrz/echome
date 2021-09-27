class VirtualMachineDoesNotExist(Exception):
    pass

class VirtualMachineTerminationException(Exception):
    pass

class VirtualMachineConfigurationException(Exception):
    pass

class InvalidLaunchConfiguration(Exception):
    pass

class LaunchError(Exception):
    pass
