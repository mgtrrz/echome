# Generated by Django 3.2.6 on 2021-09-12 18:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('identity', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='GuestImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image_id', models.CharField(db_index=True, max_length=20, unique=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('image_path', models.CharField(max_length=200)),
                ('name', models.CharField(max_length=60)),
                ('description', models.CharField(max_length=100)),
                ('minimum_requirements', models.JSONField(default=dict)),
                ('image_metadata', models.JSONField(default=dict)),
                ('deactivated', models.BooleanField(default=False)),
                ('tags', models.JSONField(default=dict)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='UserImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image_id', models.CharField(db_index=True, max_length=20, unique=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('image_path', models.CharField(max_length=200)),
                ('name', models.CharField(max_length=60)),
                ('description', models.CharField(max_length=100)),
                ('minimum_requirements', models.JSONField(default=dict)),
                ('image_metadata', models.JSONField(default=dict)),
                ('deactivated', models.BooleanField(default=False)),
                ('tags', models.JSONField(default=dict)),
                ('account', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='identity.account', to_field='account_id')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]