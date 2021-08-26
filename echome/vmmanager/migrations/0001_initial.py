# Generated by Django 3.2.6 on 2021-08-26 02:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('identity', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='HostMachines',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('host_id', models.CharField(max_length=20, unique=True)),
                ('name', models.CharField(max_length=40)),
                ('ip', models.GenericIPAddressField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('location', models.CharField(max_length=40)),
                ('tags', models.JSONField()),
            ],
        ),
        migrations.CreateModel(
            name='VirtualMachines',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('instance_id', models.CharField(max_length=20, unique=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('instance_type', models.CharField(max_length=40)),
                ('instance_size', models.CharField(max_length=40)),
                ('image_metadata', models.JSONField()),
                ('interfaces', models.JSONField()),
                ('storage', models.JSONField()),
                ('key_name', models.CharField(max_length=50)),
                ('firewall_rules', models.JSONField()),
                ('tags', models.JSONField()),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='identity.account')),
                ('host', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='vmmanager.hostmachines')),
            ],
        ),
        migrations.CreateModel(
            name='UserKeys',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key_id', models.CharField(max_length=20, unique=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=50)),
                ('service_key', models.BooleanField(default=False)),
                ('service_owner', models.CharField(max_length=40, null=True)),
                ('fingerprint', models.TextField()),
                ('public_key', models.TextField()),
                ('tags', models.JSONField()),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='identity.account')),
            ],
        ),
    ]
