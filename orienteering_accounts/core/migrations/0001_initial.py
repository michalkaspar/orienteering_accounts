# Generated by Django 3.1.3 on 2021-01-14 21:12

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Settings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('club_membership_deadline', models.DateTimeField(verbose_name='Deadline pro platbu oddílových příspěvků')),
            ],
        ),
    ]
