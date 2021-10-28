
from api.management_command import ManagementCommand
from django.core import exceptions
from django.utils.text import capfirst
from identity.models import User
from vmmanager.models import VirtualMachine
from vmmanager.vm_manager import VmManager

class Command(ManagementCommand):
    help = 'Terminate an instance. Useful for cleanup.'

    def handle(self, *args, **options):
        
        self.stdout.write(self.style.WARNING('Warning: This will terminate the instance and delete all disks and files associated with the instance.'))
        self.stdout.write(self.style.WARNING('No user checking will be done. Proceed with caution!'))
        vm_id = self.ask_for_input(VirtualMachine._meta.get_field('instance_id'))

        # If it exists in the database, grab the account and the root/primary user for the account
        try:
            vm = VirtualMachine.objects.get(instance_id=vm_id)
        except VirtualMachine.DoesNotExist:
            vm = None

        if vm:
            try:
                user = User.objects.filter(account=vm.account, is_superuser=True).first()
            except Exception:
                user = None
        else:
            user = None

        try:
            VmManager().terminate_instance(vm_id=vm_id, user=user, force=True)
            self.stdout.write(self.style.SUCCESS('Successfully terminated instance'))
        except Exception as e:
            self.stdout.write(e)
            self.stderr.write('Error: There was an error when attempting to delete the virtual machine.')