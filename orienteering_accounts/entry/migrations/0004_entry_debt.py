# Generated by Django 3.1.3 on 2021-05-10 21:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entry', '0003_entry_additional_services'),
    ]

    operations = [
        migrations.AddField(
            model_name='entry',
            name='debt',
            field=models.DecimalField(decimal_places=2, max_digits=9, null=True),
        ),
    ]
