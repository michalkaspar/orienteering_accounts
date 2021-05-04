# Generated by Django 3.1.3 on 2021-05-04 21:59

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0008_auto_20210301_2111'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='init_balance',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=9),
        )
    ]
