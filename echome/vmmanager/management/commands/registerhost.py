from api.management_command import ManagementCommand
from django.core import exceptions
from django.utils.text import capfirst
from vmmanager.models import HostMachine

class Command(ManagementCommand):
    help = 'Register a host'

    def handle(self, *args, **options):
        newhost = HostMachine()
        newhost.generate_id()

        hostname = HostMachine._meta.get_field('name')
        ip = HostMachine._meta.get_field('ip')
        
        try:
            newhost.name = self.ask_for_input(hostname)
            newhost.ip = self.ask_for_input(ip)
            newhost.save()
            self.stdout.write(self.style.SUCCESS('Successfully registered host'))
        except Exception as e:
            self.stdout.write(e)
            self.stderr.write('Error: There was an error when attempting to register the host.')