from django.core.management.base import BaseCommand, CommandError
from django.core import exceptions
from django.utils.text import capfirst
from identity.models import UserAccessAccounts

class Command(BaseCommand):
    help = 'Create an echome user access key and secret.'

    def handle(self, *args, **options):
        newkey = UserAccessAccounts()
        newkey.generate_id()

        user_id_field = UserAccessAccounts._meta.get_field('parent_user')
        verbose_field_name = user_id_field.verbose_name
        user_id = None
        
        while user_id is None:
            message = self._get_input_message(user_id_field)
            user_id = self.get_input_data(user_id_field, message)
            if user_id:
                error_msg = self._validate_acctname(user_id, verbose_field_name)
                if error_msg:
                    self.stderr.write(error_msg)
                    user_id = None
                    continue
        
        try:
            self.stdout.write(f"Creating access key for user: {user_id}")
            newkey.user_id = user_id
            key = newkey.generate_secret()
            newkey.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully created access key with secret: {key}'))
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
