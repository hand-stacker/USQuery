from django.db import migrations


def clear_bill_chunks(apps, schema_editor):
    BillChunk = apps.get_model('app', 'BillChunk')
    BillChunk.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0013_billchunk'),
    ]

    operations = [
        migrations.RunPython(clear_bill_chunks, migrations.RunPython.noop),
    ]
