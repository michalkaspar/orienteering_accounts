# Generated by Django 3.1.3 on 2021-05-10 20:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entry', '0002_entry_rent_si'),
    ]

    operations = [
        migrations.AddField(
            model_name='entry',
            name='additional_services',
            field=models.JSONField(default={}),
        ),
    ]
