# Generated by Django 3.1.3 on 2020-11-17 19:07

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('oris_id', models.PositiveIntegerField(unique=True)),
                ('name', models.CharField(max_length=255, verbose_name='Název')),
                ('date', models.DateField()),
                ('organizer_1', models.JSONField()),
                ('organizer_2', models.JSONField(default=dict)),
                ('region', models.CharField(max_length=50)),
                ('discipline', models.JSONField()),
                ('level', models.JSONField()),
                ('ranking', models.DecimalField(decimal_places=2, default=Decimal('0.0'), max_digits=3)),
                ('si_type', models.JSONField(default=dict)),
                ('cancelled', models.BooleanField(default=False)),
                ('gps_lat', models.CharField(max_length=50)),
                ('gps_lon', models.CharField(max_length=50)),
                ('venue', models.CharField(max_length=255, verbose_name='Místo')),
                ('oris_version', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('oris_classes_last_modified_timestamp', models.PositiveIntegerField(blank=True, null=True)),
                ('oris_services_last_modified_timestamp', models.PositiveIntegerField(blank=True, null=True)),
                ('oris_parent_id', models.PositiveIntegerField(blank=True, null=True)),
                ('status', models.CharField(blank=True, default='', max_length=255)),
                ('ob_postupy', models.CharField(blank=True, max_length=255, null=True)),
            ],
        ),
    ]
