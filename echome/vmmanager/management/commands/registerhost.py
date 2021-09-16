from django.core.management.base import BaseCommand, CommandError
from django.core import exceptions
from django.utils.text import capfirst
from vmmanager.models import HostMachine

class Command(BaseCommand):
    help = 'Create an echome account'

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        newacct = Account()
        newacct.generate_id()

        accountname = Account._meta.get_field('name')
        verbose_field_name = accountname.verbose_name
        name = None
        
        while name is None:
            message = self._get_input_message(accountname)
            name = self.get_input_data(accountname, message)
            if name:
                error_msg = self._validate_acctname(name, verbose_field_name)
                if error_msg:
                    self.stderr.write(error_msg)
                    name = None
                    continue
        
        try:
            newacct.name = name
            self.stdout.write(f"Creating account '{name}' with account id: {newacct.account_id}")
            newacct.save()
            self.stdout.write(self.style.SUCCESS('Successfully created account'))
        except Exception as e:
            self.stdout.write(e)
            self.stderr.write('Error: There was an error when attempting to create the account.')
    
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
