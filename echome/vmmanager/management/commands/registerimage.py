from api.management_command import ManagementCommand
from vmmanager.models import Image
from vmmanager.image_manager import ImageManager

class Command(ManagementCommand):
    help = 'Register a guest image for use by all accounts'

    def handle(self, *args, **options):
        iman = ImageManager()

        image_path = Image._meta.get_field('image_path')
        name = Image._meta.get_field('name')
        description = Image._meta.get_field('description')

        path = self.ask_for_input(image_path)
        name = self.ask_for_input(name)
        description = self.ask_for_input(description)

        try:
            iman.register_guest_image(
                path,
                name,
                description
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully registered new image: {iman.image.image_id}'))
        except Exception as e:
            self.stdout.write(e)
            self.stderr.write('Error: There was an error when attempting to register the host.')
