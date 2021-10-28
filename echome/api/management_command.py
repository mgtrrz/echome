from django.core.management.base import BaseCommand, CommandError
from django.core import exceptions
from django.utils.text import capfirst

class ManagementCommand(BaseCommand):

    def ask_for_input(self, db_field):
        field = None
        while field is None:
            message = self.get_input_message(db_field)
            field = self.get_input_data(db_field, message)
            if field:
                error_msg = self.validate_field(field, db_field.verbose_name)
                if error_msg:
                    self.stderr.write(error_msg)
                    field = None
                    continue
        
        return field

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

    def get_input_message(self, field, default=None):
        return '%s%s%s: ' % (
            capfirst(field.verbose_name),
            " (leave blank to use '%s')" % default if default else '',
            ' (%s.%s)' % (
                field.remote_field.model._meta.object_name,
                field.m2m_target_field_name() if field.many_to_many else field.remote_field.field_name,
            ) if field.remote_field else '',
        )

    def validate_field(self, field, verbose_field_name):
        if not field:
            return '%s cannot be blank.' % capfirst(verbose_field_name)
