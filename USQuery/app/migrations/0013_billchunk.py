from django.db import migrations, models
from pgvector.django import VectorExtension, VectorField


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0012_chatsession_chatmessage_and_more'),
    ]

    operations = [
        VectorExtension(),
        migrations.CreateModel(
            name='BillChunk',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('bill_id', models.IntegerField(db_index=True)),
                ('chunk_index', models.IntegerField()),
                ('content', models.TextField()),
                ('embedding', VectorField(dimensions=768)),
            ],
            options={
                'unique_together': {('bill_id', 'chunk_index')},
            },
        ),
    ]
