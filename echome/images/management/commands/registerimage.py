from api.management_command import ManagementCommand
from django.core import exceptions
from django.utils.text import capfirst
from images.models import GuestImage

class Command(ManagementCommand):
    help = 'Register a guest image for use by all accounts'

    def handle(self, *args, **options):
        new_image = GuestImage()

        image_path = GuestImage._meta.get_field('image_path')
        name = GuestImage._meta.get_field('name')
        description = GuestImage._meta.get_field('description')

        path = self.ask_for_input(image_path)
        name = self.ask_for_input(name)
        description = self.ask_for_input(description)

        try:
            new_image.register_image(
                path,
                name,
                description
            )
            self.stdout.write(self.style.SUCCESS('Successfully registered new image.'))
        except Exception as e:
            self.stdout.write(e)
            self.stderr.write('Error: There was an error when attempting to register the host.')