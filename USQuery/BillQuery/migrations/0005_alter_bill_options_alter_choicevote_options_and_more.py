# Generated by Django 4.2.7 on 2025-01-29 06:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('BillQuery', '0004_alter_bill_options_alter_choicevote_options_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='bill',
            options={'ordering': ['-origin_date', '-latest_action']},
        ),
        migrations.AlterModelOptions(
            name='choicevote',
            options={'ordering': ['-dateTime']},
        ),
        migrations.AlterModelOptions(
            name='vote',
            options={'ordering': ['-dateTime']},
        ),
    ]
