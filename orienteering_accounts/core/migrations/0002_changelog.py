# Generated by Django 3.1.3 on 2021-03-15 23:42

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChangeLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Datum a čas vzniku')),
                ('modified', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Datum a čas poslední úpravy')),
                ('instance_id', models.PositiveIntegerField()),
                ('change_type', models.CharField(choices=[('CREATE', 'Vytvořil'), ('UPDATE', 'Změnil'), ('DELETE', 'Smazal')], default='UPDATE', max_length=255)),
                ('instance_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
