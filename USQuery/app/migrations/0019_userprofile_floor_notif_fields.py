from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0018_alter_billchunk_unique_together_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='enabled_house_floor_notif',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='enabled_senate_floor_notif',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='house_floor_notif_frequency',
            field=models.SmallIntegerField(choices=[(0, 'Consistent'), (1, 'Daily')], default=1),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='senate_floor_notif_frequency',
            field=models.SmallIntegerField(choices=[(0, 'Consistent'), (1, 'Daily')], default=1),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='house_floor_notif_time',
            field=models.SmallIntegerField(
                blank=True, null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(23),
                ],
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='senate_floor_notif_time',
            field=models.SmallIntegerField(
                blank=True, null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(23),
                ],
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='house_floor_notif_timezone',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='senate_floor_notif_timezone',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
    ]
