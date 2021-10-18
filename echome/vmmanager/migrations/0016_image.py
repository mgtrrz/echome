# Generated by Django 3.2.6 on 2021-10-16 17:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('identity', '0001_initial'),
        ('vmmanager', '0015_alter_volume_virtual_machine'),
    ]

    operations = [
        migrations.CreateModel(
            name='Image',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image_type', models.CharField(choices=[('GUEST', 'Guest'), ('USER', 'User')], default='GUEST', max_length=16)),
                ('image_id', models.CharField(db_index=True, max_length=20, unique=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('image_path', models.CharField(max_length=200)),
                ('name', models.CharField(max_length=60)),
                ('description', models.CharField(max_length=100)),
                ('minimum_requirements', models.JSONField(default=dict)),
                ('metadata', models.JSONField(default=dict)),
                ('deactivated', models.BooleanField(default=False)),
                ('tags', models.JSONField(default=dict)),
                ('state', models.CharField(choices=[('CREATING', 'Creating'), ('READY', 'Ready'), ('ERROR', 'Error'), ('DELETING', 'Deleting'), ('DELETED', 'Deleted')], default='CREATING', max_length=16)),
                ('operating_system', models.CharField(choices=[('WINDOWS', 'Windows'), ('LINUX', 'Linux'), ('OTHER', 'Other'), ('NONE', 'None')], default='LINUX', max_length=12)),
                ('account', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='identity.account', to_field='account_id')),
            ],
        ),
    ]