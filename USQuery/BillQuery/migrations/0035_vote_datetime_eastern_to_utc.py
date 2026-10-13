# Data migration: correct Vote.dateTime for every existing row.
#
# Both vote parsers used to append a "Z" to the Eastern wall-clock time that the
# House clerk and Senate LIS publish, so a 9:30 PM ET vote was stored as
# 21:30 UTC instead of 01:30 UTC the next day (4-5 hours off depending on DST).
# app.utils._vote_datetime now stores real UTC; this rewrites the old rows to
# match.
#
#   forward: reinterpret the stored UTC wall clock as America/New_York
#   reverse: the exact inverse
#
# Postgres resolves the DST offset per row from the row's own date. Run it
# exactly once, together with the code that writes correct UTC: rows written by
# the new code and then run through this would be shifted twice.

from django.db import migrations

FORWARD_SQL = '''
UPDATE "BillQuery_vote"
SET "dateTime" = ("dateTime" AT TIME ZONE 'UTC') AT TIME ZONE 'America/New_York';
'''

REVERSE_SQL = '''
UPDATE "BillQuery_vote"
SET "dateTime" = ("dateTime" AT TIME ZONE 'America/New_York') AT TIME ZONE 'UTC';
'''


class Migration(migrations.Migration):

    dependencies = [
        ('BillQuery', '0034_remove_subject_name_trgm_index'),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
