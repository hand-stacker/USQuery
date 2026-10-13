"""Vote times: stored as real UTC, shown in US Eastern everywhere, and the
0035 data migration that corrects rows written before the fix."""

import datetime
import importlib
import json

import pytest
from django.db import connection
from django.utils import timezone

from BillQuery.models import US_EASTERN, Vote
from tests.factories import make_bill, make_congress, make_member, make_membership, make_vote

pytestmark = pytest.mark.django_db

UTC = datetime.timezone.utc
migration = importlib.import_module('BillQuery.migrations.0035_vote_datetime_eastern_to_utc')

# 9:30 PM Eastern on Jul 23 (EDT) and 9:30 PM Eastern on Jan 15 (EST).
SUMMER_ET = datetime.datetime(2026, 7, 23, 21, 30, tzinfo=US_EASTERN)
WINTER_ET = datetime.datetime(2026, 1, 15, 21, 30, tzinfo=US_EASTERN)


class TestMigrationSql:
    def _mislabeled(self, et):
        """What the old parsers stored: the Eastern wall clock tagged as UTC."""
        return et.replace(tzinfo=UTC)

    def _run(self, sql):
        with connection.cursor() as cursor:
            cursor.execute(sql)

    def test_forward_fixes_both_dst_seasons(self):
        summer = make_vote(num=1, when=self._mislabeled(SUMMER_ET))
        winter = make_vote(num=2, when=self._mislabeled(WINTER_ET))
        self._run(migration.FORWARD_SQL)
        summer.refresh_from_db()
        winter.refresh_from_db()
        assert summer.dateTime == datetime.datetime(2026, 7, 24, 1, 30, tzinfo=UTC)   # +4h
        assert winter.dateTime == datetime.datetime(2026, 1, 16, 2, 30, tzinfo=UTC)   # +5h
        assert (summer.getDate(), winter.getDate()) == ('2026-07-23', '2026-01-15')

    def test_reverse_is_exact_inverse(self):
        vote = make_vote(num=1, when=self._mislabeled(SUMMER_ET))
        original = Vote.objects.get(pk=vote.pk).dateTime
        self._run(migration.FORWARD_SQL)
        self._run(migration.REVERSE_SQL)
        assert Vote.objects.get(pk=vote.pk).dateTime == original

    def test_migration_wiring(self):
        assert migration.Migration.dependencies == [('BillQuery', '0034_remove_subject_name_trgm_index')]
        op = migration.Migration.operations[0]
        assert (op.sql, op.reverse_sql) == (migration.FORWARD_SQL, migration.REVERSE_SQL)


@pytest.fixture
def evening_vote():
    congress = make_congress(119, start_year=2025, end_year=2027)
    bill = make_bill(119, 4, 1)
    vote = make_vote(bill, house=False, num=7, when=SUMMER_ET)
    membership = make_membership(congress=congress, member=make_member('S000123'), house=False,
                                 start_date='2025-01-03')
    vote.yeas.add(membership)
    return vote, membership


class TestDisplay:
    def test_web_vote_page(self, client, evening_vote):
        vote, _ = evening_vote
        assert client.get(f'/vote/{vote.id}').context['vote_time'] == '2026-07-23'

    def test_search_json_has_eastern_offset(self, client, evening_vote):
        rows = client.get('/vote/search/', {'start_date': '2026-07-23', 'end_date': '2026-07-23',
                                            'bill_type': '!'}).context['votes_json']
        assert rows[0]['date'] == '2026-07-23T21:30:00-04:00'

    def test_search_window_is_eastern_day(self, client, evening_vote):
        # Stored at 01:30 UTC on Jul 24, but it happened on Jul 23 in Washington.
        rows = client.get('/vote/search/', {'start_date': '2026-07-24', 'end_date': '2026-07-24',
                                            'bill_type': '!'}).context['votes_json']
        assert rows == []

    def test_rest_membership_api(self, api_client, evening_vote, monkeypatch):
        from app import utils
        monkeypatch.setattr(utils, 'updateMember', lambda *a: None)
        _, membership = evening_vote
        data = api_client.get(f'/api/v1.0/membership-by-id/{membership.id}').json()
        assert data['vote_list'][0]['dateTime'] == '2026-07-23T21:30:00-04:00'

    def test_graphql(self, client, evening_vote):
        vote, _ = evening_vote
        body = client.post('/api/v1.0/graphql/', json.dumps({'query': f'{{ getVote(voteId: {vote.id}) {{ dateTime }} }}'}),
                           content_type='application/json').json()
        assert body['data']['getVote']['dateTime'] == '2026-07-23T21:30:00-04:00'

    def test_recent_votes_cursor_still_paginates(self, client, evening_vote):
        make_vote(make_bill(119, 4, 2), num=8, when=SUMMER_ET - datetime.timedelta(hours=1))
        query = '''query($after: String) { getRecentVotes(first: 1, after: $after) {
            edges { node { id } } pageInfo { endCursor } } }'''
        first = client.post('/api/v1.0/graphql/', json.dumps({'query': query}), content_type='application/json').json()
        cursor = first['data']['getRecentVotes']['pageInfo']['endCursor']
        second = client.post('/api/v1.0/graphql/', json.dumps({'query': query, 'variables': {'after': cursor}}),
                             content_type='application/json').json()
        ids = [first['data']['getRecentVotes']['edges'][0]['node']['id'],
               second['data']['getRecentVotes']['edges'][0]['node']['id']]
        assert len(set(ids)) == 2
