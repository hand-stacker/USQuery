from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0019_userprofile_floor_notif_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='web_searches',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
