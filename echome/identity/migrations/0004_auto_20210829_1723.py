# Generated by Django 3.2.6 on 2021-08-29 17:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('identity', '0003_alter_account_secret'),
    ]

    operations = [
        migrations.AlterModelManagers(
            name='user',
            managers=[
            ],
        ),
        migrations.AlterField(
            model_name='user',
            name='secret',
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name='useraccessaccounts',
            name='secret',
            field=models.TextField(null=True),
        ),
    ]
