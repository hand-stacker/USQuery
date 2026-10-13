import django.contrib.postgres.indexes
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations

# Codifies DB objects that were previously created by hand directly in psql:
# - the pg_trgm extension (already installed, version 1.6, on the live DB)
# - the bill_search_vector_update() trigger function + bill_search_vector_trigger
#   (title weight A, policy_area weight B) that populate Bill.search_vector
# Bringing these into a migration means a fresh database (new dev setup, CI,
# disaster recovery) gets the same full-text search behavior automatically.

CREATE_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION public.bill_search_vector_update()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    NEW.search_vector := setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A')
        || setweight(to_tsvector('english', coalesce(NEW.policy_area, '')), 'B');
    RETURN NEW;
END
$function$;

DROP TRIGGER IF EXISTS bill_search_vector_trigger ON "BillQuery_bill";

CREATE TRIGGER bill_search_vector_trigger
BEFORE INSERT OR UPDATE ON "BillQuery_bill"
FOR EACH ROW EXECUTE FUNCTION bill_search_vector_update();
"""

DROP_TRIGGER_SQL = """
DROP TRIGGER IF EXISTS bill_search_vector_trigger ON "BillQuery_bill";
DROP FUNCTION IF EXISTS public.bill_search_vector_update();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('BillQuery', '0032_bill_latest_api_update'),
    ]

    operations = [
        TrigramExtension(),
        migrations.RunSQL(sql=CREATE_TRIGGER_SQL, reverse_sql=DROP_TRIGGER_SQL),
        migrations.AddIndex(
            model_name='bill',
            index=django.contrib.postgres.indexes.GinIndex(
                fields=['title'], name='billquery_title_trgm_gin', opclasses=['gin_trgm_ops']
            ),
        ),
        migrations.AddIndex(
            model_name='subject',
            index=django.contrib.postgres.indexes.GinIndex(
                fields=['name'], name='billquery_subj_name_trgm', opclasses=['gin_trgm_ops']
            ),
        ),
    ]
