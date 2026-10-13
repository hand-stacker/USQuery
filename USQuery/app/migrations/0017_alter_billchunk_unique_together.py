from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0016_billchunk_document_type_billchunk_source_id'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='billchunk',
            unique_together={('bill_id', 'source_id', 'chunk_index')},
        ),
    ]
