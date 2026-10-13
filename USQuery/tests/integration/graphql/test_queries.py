"""GraphQL read API (/api/v1.0/graphql/) as the mobile app calls it."""

import datetime
import json
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from BillQuery.models import Subject
from notifications.models import StarredBill
from strawberryAPI.graphql import queries
from tests.factories import make_bill, make_congress, make_member, make_membership, make_vote

pytestmark = pytest.mark.django_db

URL = '/api/v1.0/graphql/'


def gql(client, query, variables=None):
    resp = client.post(URL, json.dumps({'query': query, 'variables': variables or {}}),
                       content_type='application/json')
    return resp.json()


@pytest.fixture
def data():
    congress = make_congress(119, start_year=2025, end_year=2027)
    sponsor = make_membership(congress=congress, member=make_member(first='Ann', last='Sponsor'),
                              state='CA', party='Democratic')
    cosponsor = make_membership(congress=congress, member=make_member(first='Bo', last='Co'),
                                state='TX', party='Republican')
    health = Subject.objects.create(name='Health')
    bills = []
    for n in range(1, 8):
        b = make_bill(119, 4, n, sponsor=sponsor, title=f'Bill number {n}',
                      latest_action=datetime.date(2026, 1, n))
        bills.append(b)
    bills[0].cosponsors.add(cosponsor)
    bills[0].subjects.add(health)
    bills[2].subjects.add(health)
    votes = [make_vote(bills[0], house=True, num=n,
                       when=timezone.make_aware(datetime.datetime(2026, 1, n, 12))) for n in range(1, 5)]
    votes[0].yeas.add(sponsor)
    votes[0].nays.add(cosponsor)
    return {'bills': bills, 'votes': votes, 'health': health, 'sponsor': sponsor}


class TestSimpleQueries:
    def test_congress_and_subjects(self, client, data):
        result = gql(client, '{ getCongressSet { congressNum startYear } getSubjectSet { id name } }')
        assert result['data']['getCongressSet'] == [{'congressNum': 119, 'startYear': 2025}]
        assert result['data']['getSubjectSet'] == [{'id': str(data['health'].id), 'name': 'Health'}]

    def test_get_bill(self, client, data):
        bill = data['bills'][0]
        summary = {'_id': bill.id, 'AI_generated_content?': True, 'summary': '<p>A <b>bill</b></p>',
                   'generated_at': datetime.date(2026, 2, 1)}
        actions = {'actions': [{'actionCode': '1000', 'actionDate': '2026-01-01', 'text': 'Introduced', 'type': 'IntroReferral'},
                               {'actionCode': '8000', 'actionDate': '2026-01-05', 'text': 'Passed', 'type': 'Floor',
                                'recordedVotes': [{'chamber': 'House', 'congress': 119, 'sessionNumber': 2, 'rollNumber': 42}]}]}
        with mock.patch.object(queries, 'fetch_summary', mock.AsyncMock(return_value=summary)), \
             mock.patch.object(queries, 'fetch_actions', mock.AsyncMock(return_value=actions)):
            result = gql(client, '''query($id: Int!) { getBill(billId: $id) {
                id title summary isAiGenerated aiSummaryGeneratedAt
                sponsor { name party state } cosponsors { name }
                subjects { name } actions { actionCode voteId text } } }''', {'id': bill.id})
        got = result['data']['getBill']
        assert got['title'] == 'Bill number 1'
        assert got['summary'].strip() == 'A **bill**'
        assert got['isAiGenerated'] is True and got['aiSummaryGeneratedAt'] == '2026-02-01'
        assert got['sponsor'] == {'name': 'Ann Sponsor', 'party': 'Democratic', 'state': 'CA'}
        assert got['cosponsors'] == [{'name': 'Bo Co'}]
        assert [a['voteId'] for a in got['actions']] == [None, 119_1_2_00042]

    def test_get_bill_unknown(self, client, data):
        assert gql(client, '{ getBill(billId: 1) { id } }')['data']['getBill'] is None

    def test_get_vote(self, client, data):
        vote = data['votes'][0]
        result = gql(client, '''query($id: Int!) { getVote(voteId: $id) {
            question bill { title } yeas { member { fullName } } nays { party } } }''', {'id': vote.id})
        got = result['data']['getVote']
        assert got['bill']['title'] == 'Bill number 1'
        assert got['yeas'] == [{'member': {'fullName': 'Ann Sponsor'}}]
        assert got['nays'] == [{'party': 'Republican'}]


class TestPagination:
    QUERY = '''query($after: String, $first: Int!) {
        getRecommendedBills(first: $first, after: $after) {
            edges { cursor node { id } } pageInfo { hasNextPage endCursor } } }'''




    def test_recent_votes(self, client, data):
        result = gql(client, '{ getRecentVotes(first: 2) { edges { node { id } } pageInfo { hasNextPage } } }')
        page = result['data']['getRecentVotes']
        assert [int(e['node']['id']) for e in page['edges']] == [data['votes'][3].id, data['votes'][2].id]
        assert page['pageInfo']['hasNextPage'] is True



class TestStarredBills:
    QUERY = '''query($t: String) { getStarredBills(accessToken: $t, first: 10) {
        error edges { node { id } } } }'''

    def test_missing_token_returns_error_in_payload(self, client, data):
        result = gql(client, self.QUERY)
        assert 'errors' not in result
        assert result['data']['getStarredBills']['error'] == 'Session expired. Please log in.'

    def test_bad_token(self, client, data):
        got = gql(client, self.QUERY, {'t': 'garbage'})['data']['getStarredBills']
        assert got['edges'] == [] and got['error'] != 'None'

    def test_valid_token(self, client, data, free_user):
        for b in data['bills'][:2]:
            StarredBill.objects.create(user_profile=free_user.userprofile, bill_id=str(b.id))
        token = str(RefreshToken.for_user(free_user).access_token)
        got = gql(client, self.QUERY, {'t': token})['data']['getStarredBills']
        assert got['error'] == 'None'
        assert [int(e['node']['id']) for e in got['edges']] == [data['bills'][1].id, data['bills'][0].id]


class TestSchemaLimits:
    def test_depth_limiter_configured(self):
        from strawberry.extensions import QueryDepthLimiter
        from strawberryAPI.graphql.schema import schema
        limiters = [e for e in schema.extensions if isinstance(e, QueryDepthLimiter)]
        assert len(limiters) == 1

    def test_deepest_real_query_allowed(self, client, data):
        # Root fields count as depth 0, so max_depth=5 admits six levels -- the
        # deepest path the current schema has.
        result = gql(client, '{ getRecentVotes(first: 1) { edges { node { yeas { member { fullName } } } } } }')
        assert 'errors' not in result

    def test_batching_capped_at_three(self, client, data):
        op = {'query': '{ getCongressSet { congressNum } }'}
        ok = client.post(URL, json.dumps([op] * 3), content_type='application/json')
        too_many = client.post(URL, json.dumps([op] * 4), content_type='application/json')
        assert ok.status_code == 200 and len(ok.json()) == 3
        assert too_many.status_code == 400
