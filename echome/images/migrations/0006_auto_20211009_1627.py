# Generated by Django 3.2.6 on 2021-10-09 16:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('images', '0005_auto_20211009_1618'),
    ]

    operations = [
        migrations.AlterField(
            model_name='guestimage',
            name='operating_system',
            field=models.CharField(choices=[('WINDOWS', 'Windows'), ('LINUX', 'Linux'), ('OTHER', 'Other'), ('NONE', 'None')], default='LINUX', max_length=12),
        ),
        migrations.AlterField(
            model_name='userimage',
            name='operating_system',
            field=models.CharField(choices=[('WINDOWS', 'Windows'), ('LINUX', 'Linux'), ('OTHER', 'Other'), ('NONE', 'None')], default='LINUX', max_length=12),
        ),
    ]