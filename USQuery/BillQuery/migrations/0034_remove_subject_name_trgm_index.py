import django.contrib.postgres.indexes
from django.db import migrations

# billquery_subj_name_trgm (added in 0033) turned out to be a net loss: Subject
# is a small, slow-growing controlled vocabulary (1,032 rows / 64 kB table),
# and the GIN trigram index itself is 200 kB -- over 3x the table size -- while
# providing no query benefit at this scale. Forcing the planner to use it
# (SET enable_seqscan = off) showed its own cost estimate (30.10) is higher
# than the plain sequential scan Postgres already picks (20.90). Removing it
# to stop paying storage + write overhead for an index that's never chosen
# and wouldn't help even if it were.
#
# Bill.title's trigram index (billquery_title_trgm_gin) is unaffected -- at
# 119k+ rows it's confirmed to be picked naturally by the planner.


class Migration(migrations.Migration):

    dependencies = [
        ('BillQuery', '0033_trigram_search_indexes'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='subject',
            name='billquery_subj_name_trgm',
        ),
    ]
