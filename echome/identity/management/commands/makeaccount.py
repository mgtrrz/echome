from django.core.management.base import BaseCommand, CommandError
from identity.models import Account

class Command(BaseCommand):
    help = 'Create an echome account'

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Successfully'))