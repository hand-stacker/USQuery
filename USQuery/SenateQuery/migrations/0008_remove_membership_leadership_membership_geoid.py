# Generated by Django 4.2.7 on 2025-02-12 02:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('SenateQuery', '0007_alter_congress_options_alter_member_options_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='membership',
            name='leadership',
        ),
        migrations.AddField(
            model_name='membership',
            name='geoid',
            field=models.CharField(blank=True, max_length=4, null=True),
        ),
    ]
