"""Member pages and the /api/v1.0/membership* mobile contract.

utils.updateMember (Congress.gov) is patched; the vote list and per-member
vote resolution run against the DB.
"""

import datetime
from unittest import mock

import pytest
from django.utils import timezone

from app import utils
from notifications.models import StarredMembership
from tests.factories import jwt_headers, make_bill, make_congress, make_member, make_membership, make_vote

pytestmark = pytest.mark.django_db

API_MEMBER = {'member': {'partyHistory': [{'partyName': 'Democratic', 'startYear': 2019}],
                         'leadership': [], 'terms': []}}


@pytest.fixture(autouse=True)
def update_member():
    with mock.patch.object(utils, 'updateMember', return_value=API_MEMBER) as m:
        yield m


@pytest.fixture
def senator():
    congress = make_congress(119, start_year=2025)
    member = make_member('S000123', first='Pat', last='Lee')
    membership = make_membership(congress=congress, member=member, house=False, state='CA',
                                 party='Democratic', start_date='2025-01-03')
    bill = make_bill(119, 0, 1)
    votes = []
    for n in range(20):
        v = make_vote(bill, house=False, num=n + 1,
                      when=timezone.make_aware(datetime.datetime(2025, 2, 1) + datetime.timedelta(days=n)))
        votes.append(v)
    votes[-1].yeas.add(membership)   # newest vote, first on page 1
    votes[-2].nays.add(membership)
    make_vote(bill, house=True, num=99)  # House vote: must not appear for a senator
    return membership


class TestMembershipApi:
    def test_by_id_payload(self, api_client, senator):
        resp = api_client.get(f'/api/v1.0/membership-by-id/{senator.id}')
        assert resp.status_code == 200
        data = resp.json()
        assert data['full_name'] == 'Pat Lee' and data['state'] == 'CA'
        assert len(data['vote_list']) == 15
        assert [v['mem_vote'] for v in data['vote_list'][:3]] == ['Yea', 'Nay', 'No Vote']
        assert data['external_party_history'] == API_MEMBER['member']['partyHistory']
        assert data['prev'] is None
        assert data['next'].endswith(f'/api/v1.0/membership-by-id/{senator.id}?page=2')

    def test_second_page(self, api_client, senator):
        data = api_client.get(f'/api/v1.0/membership-by-id/{senator.id}', {'page': 2}).json()
        assert len(data['vote_list']) == 5
        assert data['next'] is None and data['prev'].endswith('?page=1')

    def test_upstream_failure_degrades(self, api_client, senator, update_member):
        update_member.return_value = None
        data = api_client.get(f'/api/v1.0/membership-by-id/{senator.id}').json()
        assert 'external_party_history' not in data

    def test_unknown_id(self, api_client):
        assert api_client.get('/api/v1.0/membership-by-id/999').status_code == 404

    def test_by_congress_and_bioguide(self, api_client, senator):
        resp = api_client.get('/api/v1.0/membership/119/S000123/0/')
        assert resp.status_code == 200 and resp.json()['full_name'] == 'Pat Lee'
        assert api_client.get('/api/v1.0/membership/119/S000123/1/').status_code == 404

    def test_set(self, api_client, senator):
        make_membership(congress=senator.congress, house=False, state='TX')
        data = api_client.get('/api/v1.0/membership-set/119/Senate/CA/').json()
        assert [m['id'] for m in data['members']] == [senator.id]
        assert len(api_client.get('/api/v1.0/membership-set/119/Senate/All/').json()['members']) == 2

    def test_set_unknown_congress(self, api_client):
        assert api_client.get('/api/v1.0/membership-set/1/Senate/All/').status_code == 404

    def test_update_members_unknown_congress(self, client):
        assert client.get('/member/update-mems/1/Senate/All/').status_code == 404

    def test_starred_requires_jwt(self, api_client, senator, free_user):
        assert api_client.get('/api/v1.0/memberships/').status_code == 401
        StarredMembership.objects.create(user_profile=free_user.userprofile, membership_id=senator.id)
        api_client.credentials(**jwt_headers(free_user))
        assert [m['id'] for m in api_client.get('/api/v1.0/memberships/').json()['members']] == [senator.id]


class TestMemberPages:
    def test_results_page(self, client, senator):
        resp = client.get('/member/results/', {'congress': 119, 'member': 'S000123', 'chamber': 'Senate'})
        assert resp.status_code == 200
        ctx = resp.context
        assert (ctx['rep_title'], ctx['rep_state'], ctx['congress_suffix']) == ('Senator', 'California', 'th')
        assert '>Yea<' in ctx['vote_table']
        assert ctx['isStarred'] is False

    def test_results_starred_flag(self, client, senator, free_user):
        StarredMembership.objects.create(user_profile=free_user.userprofile, membership_id=senator.id)
        client.force_login(free_user)
        resp = client.get('/member/results/', {'congress': 119, 'member': 'S000123', 'chamber': 'Senate'})
        assert resp.context['isStarred'] is True

    @pytest.mark.parametrize('params', [{}, {'congress': 'abc', 'member': 'x', 'chamber': 'Senate'}])
    def test_malformed(self, client, params):
        make_congress(119)
        assert client.get('/member/results/', params).status_code == 400

    def test_member_form_requires_congress_119(self):
        # Current behavior: MemberForm.__init__ looks up Congress 119 unguarded.
        from app.forms import MemberForm
        from SenateQuery.models import Congress
        with pytest.raises(Congress.DoesNotExist):
            MemberForm()

    @pytest.mark.parametrize('params', [
        {'congress': 111, 'member': 'S000123', 'chamber': 'Senate'},
        {'congress': 119, 'member': 'NOPE', 'chamber': 'Senate'},
    ])
    def test_search_failed(self, client, senator, params):
        resp = client.get('/member/results/', params)
        assert 'SenateQuery/search_failed.html' in [t.name for t in resp.templates]

    def test_filtered_memberships_json(self, client, senator):
        data = client.get('/member/get-filtered/119/Senate/CA/').json()
        assert data['members'][0]['membership_id'] == senator.id
        assert data['members'][0]['is_active'] is True
        assert client.get('/member/get-filtered/1/Senate/CA/').json() == {'members': []}

    def test_update_members_json(self, client, senator):
        data = client.get('/member/update-mems/119/Senate/All/').json()
        assert data == {'members': [{'id': 'S000123', 'full_name': 'Pat Lee'}]}
