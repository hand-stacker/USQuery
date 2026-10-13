from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('BillQuery', '0031_billsummary_generated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='bill',
            name='latest_api_update',
            field=models.DateField(null=True, blank=True, db_index=True),
        ),
    ]
