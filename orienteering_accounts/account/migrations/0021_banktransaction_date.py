# Generated by Django 3.2.18 on 2024-06-29 09:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0020_banktransaction'),
    ]

    operations = [
        migrations.AddField(
            model_name='banktransaction',
            name='date',
            field=models.DateTimeField(default=None, verbose_name='Datum'),
            preserve_default=False,
        ),
    ]
