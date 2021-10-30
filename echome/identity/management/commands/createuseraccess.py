from django.core.management.base import BaseCommand, CommandError
from django.core import exceptions
from django.utils.text import capfirst
from identity.models import User, Account

class Command(BaseCommand):
    help = 'Create an echome user access key and secret.'

    def handle(self, *args, **options):
        newkey = User()

        newkey.type = User.Type.ACCESS_KEY
        newkey.generate_id()

        parent_field = User._meta.get_field('parent')
        verbose_field_name = parent_field.verbose_name
        parent_user_id = None
        
        while parent_user_id is None:
            message = self._get_input_message(parent_field)
            parent_user_id = self.get_input_data(parent_field, message)
            if parent_user_id:
                error_msg = self._validate_acctname(parent_user_id, verbose_field_name)
                if error_msg:
                    self.stderr.write(error_msg)
                    parent_user_id = None
                    continue
        
        # Setting parent user
        newkey.parent = User.objects.get(user_id=parent_user_id)
        if newkey.parent is None:
            self.stderr.write('Error: No user found with that ID.')
            exit(1)
        
        # Setting account based off parent user's account
        newkey.account = Account.objects.get(account_id=newkey.parent.account_id)

        # Setting the username the same as the user_id
        newkey.username = newkey.user_id

        try:
            self.stdout.write(f"Creating access key for user: {parent_user_id}")
            key = newkey.generate_secret()
            newkey.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully created access key for user: {parent_user_id}'))
            self.stdout.write(f'Access ID: {newkey.user_id}')
            self.stdout.write(f'Secret Key: {key}')
        except Exception as e:
            self.stdout.write(e)
            self.stderr.write('Error: There was an error when attempting to create the access key.')
    

    def get_input_data(self, field, message, default=None):
        """
        Override this method if you want to customize data inputs or
        validation exceptions.
        """
        raw_value = input(message)
        if default and raw_value == '':
            raw_value = default
        try:
            val = field.clean(raw_value, None)
        except exceptions.ValidationError as e:
            self.stderr.write("Error: %s" % '; '.join(e.messages))
            val = None

        return val


    def _get_input_message(self, field, default=None):
        return '%s%s%s: ' % (
            capfirst(field.verbose_name),
            " (leave blank to use '%s')" % default if default else '',
            ' (%s.%s)' % (
                field.remote_field.model._meta.object_name,
                field.m2m_target_field_name() if field.many_to_many else field.remote_field.field_name,
            ) if field.remote_field else '',
        )


    def _validate_acctname(self, acctname, verbose_field_name):
        """Validate username. If invalid, return a string error message."""
        if not acctname:
            return '%s cannot be blank.' % capfirst(verbose_field_name)
