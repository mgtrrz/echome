
from api.management_command import ManagementCommand
from identity.models import User
from kube.manager import KubeClusterManager

class Command(ManagementCommand):
    help = 'Create a Kubernetes Base image.'

    def handle(self, *args, **options):
        
        raw_kube_version = input("Specify Kubernetes version: ")
        print(raw_kube_version)
        kube_version = raw_kube_version.strip()

        raw_base_image = input("Specify base image: ")
        print(raw_base_image)
        base_image = raw_base_image.strip()
        
        user = User.objects.get(username="mark")
        clustermanager = KubeClusterManager()

        try:
            clustermanager.generate_kubernetes_image(user, base_image, "home-network", kube_version)
            self.stdout.write(self.style.SUCCESS('Successfully'))
        except Exception as e:
            self.stdout.write(e)
            self.stderr.write('Error: There was an error while attempting to create the Kubernetes base image.')
