from django.db import migrations
from pgvector.django import VectorField


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0014_clear_billchunks'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billchunk',
            name='embedding',
            field=VectorField(dimensions=1024),
        ),
    ]
