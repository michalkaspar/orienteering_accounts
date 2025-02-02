# Generated by Django 3.2.18 on 2024-06-29 09:21

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0019_account_email2'),
    ]

    operations = [
        migrations.CreateModel(
            name='BankTransaction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Datum a čas vzniku')),
                ('modified', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Datum a čas poslední úpravy')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=9, verbose_name='Částka')),
                ('charged', models.BooleanField(default=False, verbose_name='Zúčtováno')),
                ('transaction_data', models.JSONField(verbose_name='Data transakce')),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bank_transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
