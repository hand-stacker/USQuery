"""notifications/views.py: the mobile star / device / preference APIs.

Every JWT endpoint has three gates: authenticated, JWT (not session), and
user.is_active. The third is easy to regress, so it's asserted per endpoint.
"""

import pytest

from notifications.models import Device, FavoriteSubject, StarredBill, StarredMembership
from tests.factories import jwt_headers, make_user

pytestmark = pytest.mark.django_db

JWT_ENDPOINTS = [
    ('/api/notif/register-device/', {'device_token': 't', 'platform': 'ios'}),
    ('/api/notif/unregister-device/', {'device_token': 't'}),
    ('/api/notif/star-bill/', {'bill_id': '11940001'}),
    ('/api/notif/unstar-bill/', {'bill_id': '11940001'}),
    ('/api/notif/star-membership/', {'membership_id': 1}),
    ('/api/notif/unstar-membership/', {'membership_id': 1}),
    ('/api/notif/update-favorites/', {'subject_ids': [1]}),
    ('/api/notif/update-floor-preferences/', {'house': True}),
]


@pytest.fixture
def client(api_client, free_user):
    api_client.credentials(**jwt_headers(free_user))
    api_client.user = free_user
    return api_client


def _post(client, url, data):
    return client.post(url, data, format='json')


class TestGates:
    @pytest.mark.parametrize('url, data', JWT_ENDPOINTS)
    def test_anonymous_rejected(self, api_client, url, data):
        assert _post(api_client, url, data).status_code == 401

    @pytest.mark.parametrize('url, data', JWT_ENDPOINTS)
    def test_unverified_user_rejected(self, api_client, url, data):
        api_client.credentials(**jwt_headers(make_user(active=False)))
        resp = _post(api_client, url, data)
        assert resp.status_code in (401, 403)

    @pytest.mark.parametrize('url, data', JWT_ENDPOINTS)
    def test_session_login_not_enough(self, api_client, free_user, url, data):
        api_client.force_login(free_user)
        assert _post(api_client, url, data).status_code == 401

    @pytest.mark.parametrize('url', ['/api/notif/star-bill/', '/api/notif/update-floor-preferences/'])
    def test_get_not_allowed(self, client, url):
        assert client.get(url).status_code == 405


class TestDevices:
    def test_register(self, client):
        resp = _post(client, '/api/notif/register-device/', {'device_token': 'abc', 'platform': 'ios'})
        assert resp.status_code == 201
        assert Device.objects.get(device_token='abc').user_profile.user == client.user

    def test_missing_fields(self, client):
        assert _post(client, '/api/notif/register-device/', {'device_token': 'abc'}).status_code == 400

    def test_unregister_then_reregister(self, client):
        _post(client, '/api/notif/register-device/', {'device_token': 'abc', 'platform': 'ios'})
        assert _post(client, '/api/notif/unregister-device/', {'device_token': 'abc'}).status_code == 202
        assert not Device.objects.get(device_token='abc').is_active
        assert _post(client, '/api/notif/register-device/', {'device_token': 'abc', 'platform': 'ios'}).status_code == 201
        assert Device.objects.get(device_token='abc').is_active

    def test_reregistering_active_device_is_idempotent(self, client):
        # The app registers its push token on every launch.
        _post(client, '/api/notif/register-device/', {'device_token': 'abc', 'platform': 'ios'})
        resp = _post(client, '/api/notif/register-device/', {'device_token': 'abc', 'platform': 'ios'})
        assert resp.status_code == 201
        assert Device.objects.filter(device_token='abc', is_active=True).count() == 1

    def test_token_moves_to_new_account(self, client):
        # Same phone, different user signed in.
        _post(client, '/api/notif/register-device/', {'device_token': 'abc', 'platform': 'ios'})
        other = make_user()
        client.credentials(**jwt_headers(other))
        assert _post(client, '/api/notif/register-device/', {'device_token': 'abc', 'platform': 'ios'}).status_code == 201
        assert Device.objects.get(device_token='abc').user_profile.user == other

    def test_reregistering_at_limit_is_allowed(self, client):
        for i in range(5):
            _post(client, '/api/notif/register-device/', {'device_token': f't{i}', 'platform': 'ios'})
        assert _post(client, '/api/notif/register-device/', {'device_token': 't0', 'platform': 'ios'}).status_code == 201

    def test_device_limit(self, client):
        for i in range(5):
            _post(client, '/api/notif/register-device/', {'device_token': f't{i}', 'platform': 'ios'})
        resp = _post(client, '/api/notif/register-device/', {'device_token': 'extra', 'platform': 'ios'})
        assert resp.status_code == 403


class TestStarring:
    def test_star_and_unstar_bill(self, client):
        assert _post(client, '/api/notif/star-bill/', {'bill_id': '11940001'}).status_code == 201
        assert StarredBill.objects.get(bill_id='11940001').is_active
        assert _post(client, '/api/notif/unstar-bill/', {'bill_id': '11940001'}).status_code == 202
        assert not StarredBill.objects.get(bill_id='11940001').is_active
        assert _post(client, '/api/notif/star-bill/', {'bill_id': '11940001'}).status_code == 201
        assert StarredBill.objects.get(bill_id='11940001').is_active

    def test_restarring_active_bill_is_idempotent(self, client):
        _post(client, '/api/notif/star-bill/', {'bill_id': '11940001'})
        assert _post(client, '/api/notif/star-bill/', {'bill_id': '11940001'}).status_code == 201
        assert StarredBill.objects.filter(bill_id='11940001').count() == 1

    def test_restarring_at_limit_is_allowed(self, client):
        for i in range(10):
            _post(client, '/api/notif/star-bill/', {'bill_id': str(i + 1)})
        assert _post(client, '/api/notif/star-bill/', {'bill_id': '1'}).status_code == 201

    def test_reactivating_over_limit_is_rejected(self, client):
        for i in range(10):
            _post(client, '/api/notif/star-bill/', {'bill_id': str(i + 1)})
        _post(client, '/api/notif/unstar-bill/', {'bill_id': '1'})
        _post(client, '/api/notif/star-bill/', {'bill_id': '11'})
        assert _post(client, '/api/notif/star-bill/', {'bill_id': '1'}).status_code == 403

    def test_restarring_membership_is_idempotent(self, client):
        _post(client, '/api/notif/star-membership/', {'membership_id': 7})
        assert _post(client, '/api/notif/star-membership/', {'membership_id': 7}).status_code == 201

    def test_bill_limit_returns_403_with_message(self, client):
        for i in range(10):
            _post(client, '/api/notif/star-bill/', {'bill_id': str(i + 1)})
        resp = _post(client, '/api/notif/star-bill/', {'bill_id': '999'})
        assert resp.status_code == 403
        assert 'at most 10 starred bills' in str(resp.data['error'])

    def test_star_membership(self, client):
        assert _post(client, '/api/notif/star-membership/', {'membership_id': 7}).status_code == 201
        assert _post(client, '/api/notif/unstar-membership/', {'membership_id': 7}).status_code == 202
        assert not StarredMembership.objects.get(membership_id=7).is_active

    @pytest.mark.parametrize('url', ['/api/notif/star-bill/', '/api/notif/star-membership/',
                                     '/api/notif/unstar-bill/', '/api/notif/unstar-membership/'])
    def test_missing_id(self, client, url):
        assert _post(client, url, {}).status_code == 400

    def test_users_are_isolated(self, client):
        other = make_user()
        _post(client, '/api/notif/star-bill/', {'bill_id': '11940001'})
        client.credentials(**jwt_headers(other))
        _post(client, '/api/notif/unstar-bill/', {'bill_id': '11940001'})
        assert StarredBill.objects.get(bill_id='11940001').is_active


class TestFavoriteSubjects:
    def _ids(self, user):
        return set(FavoriteSubject.objects.filter(user_profile__user=user, is_active=True)
                   .values_list('subject_id', flat=True))

    def test_diff_update(self, client):
        assert _post(client, '/api/notif/update-favorites/', {'subject_ids': [1, 2, 3]}).status_code == 202
        assert self._ids(client.user) == {1, 2, 3}
        _post(client, '/api/notif/update-favorites/', {'subject_ids': [2, 4]})
        assert self._ids(client.user) == {2, 4}
        _post(client, '/api/notif/update-favorites/', {'subject_ids': [1]})
        assert self._ids(client.user) == {1}
        assert FavoriteSubject.objects.filter(user_profile__user=client.user).count() == 4

    def test_empty_list_clears(self, client):
        _post(client, '/api/notif/update-favorites/', {'subject_ids': [1, 2]})
        _post(client, '/api/notif/update-favorites/', {'subject_ids': []})
        assert self._ids(client.user) == set()

    @pytest.mark.parametrize('data', [{}, {'subject_ids': None}, {'subject_ids': 5},
                                      {'subject_ids': ['a']}, {'subject_ids': [True]}])
    def test_bad_subject_ids(self, client, data):
        assert _post(client, '/api/notif/update-favorites/', data).status_code == 400


class TestNotifPreferences:
    def test_no_fields_is_noop(self, client):
        assert _post(client, '/api/notif/update-preferences/', {}).status_code == 202

    def test_toggle_bill_notifications(self, client):
        assert _post(client, '/api/notif/update-preferences/', {'bill': False}).status_code == 202
        client.user.userprofile.refresh_from_db()
        assert client.user.userprofile.enabled_bill_notif is False
        assert client.user.userprofile.enabled_subject_notif is True

    def test_toggle_both(self, client):
        _post(client, '/api/notif/update-preferences/', {'bill': False, 'subject': False})
        _post(client, '/api/notif/update-preferences/', {'subject': True})
        profile = client.user.userprofile
        profile.refresh_from_db()
        assert (profile.enabled_bill_notif, profile.enabled_subject_notif) == (False, True)

    def test_form_encoded_false_string(self, client):
        client.post('/api/notif/update-preferences/', {'bill': 'false'})
        client.user.userprofile.refresh_from_db()
        assert client.user.userprofile.enabled_bill_notif is False


class TestFloorPreferences:
    URL = '/api/notif/update-floor-preferences/'

    def test_first_enable_defaults_time_and_tz(self, client):
        assert _post(client, self.URL, {'house': True}).status_code == 202
        profile = client.user.userprofile
        profile.refresh_from_db()
        assert profile.enabled_house_floor_notif
        assert 0 <= profile.house_floor_notif_time <= 23
        assert profile.house_floor_notif_timezone == 'UTC'

    def test_full_update(self, client):
        resp = _post(client, self.URL, {
            'senate': True, 'senate_frequency': 0, 'senate_time': 7, 'senate_timezone': 'pst',
        })
        assert resp.status_code == 202
        profile = client.user.userprofile
        profile.refresh_from_db()
        assert (profile.senate_floor_notif_frequency, profile.senate_floor_notif_time,
                profile.senate_floor_notif_timezone) == (0, 7, 'PST')

    def test_timezone_truncated(self, client):
        _post(client, self.URL, {'house_timezone': 'America/Los_Angeles'})
        client.user.userprofile.refresh_from_db()
        assert client.user.userprofile.house_floor_notif_timezone == 'AMERICA/LO'

    @pytest.mark.parametrize('data', [
        {'house_time': 24}, {'house_time': -1}, {'house_time': '5'}, {'house_time': True},
        {'senate_time': 3.5}, {'house_frequency': 2}, {'senate_frequency': 'daily'},
    ])
    def test_invalid_values(self, client, data):
        assert _post(client, self.URL, data).status_code == 400


class TestGetPreferences:
    def test_payload(self, client):
        _post(client, '/api/notif/star-bill/', {'bill_id': '11940001'})
        _post(client, '/api/notif/star-bill/', {'bill_id': 'not-a-number'})
        _post(client, '/api/notif/star-membership/', {'membership_id': 5})
        _post(client, '/api/notif/update-favorites/', {'subject_ids': [9]})
        resp = client.get('/api/notif/get-preferences/')
        assert resp.status_code == 202
        assert resp.data['bill_ids'] == [11940001]
        assert resp.data['membership_ids'] == [5]
        assert resp.data['subject_ids'] == [9]
        assert resp.data['enabled_bill_notif'] is True

    def test_anonymous(self, api_client):
        assert api_client.get('/api/notif/get-preferences/').status_code == 401


class TestInternalSessionEndpoints:
    def test_session_works(self, api_client, free_user):
        api_client.force_login(free_user)
        assert api_client.post('/star-item/', {'bill_id': '11940001', 'membership_id': 3}).status_code == 201
        assert StarredBill.objects.filter(bill_id='11940001', is_active=True).exists()
        assert StarredMembership.objects.filter(membership_id=3, is_active=True).exists()
        assert api_client.post('/unstar-item/', {'bill_id': '11940001'}).status_code == 202
        assert not StarredBill.objects.get(bill_id='11940001').is_active

    def test_jwt_does_not_work(self, api_client, free_user):
        api_client.credentials(**jwt_headers(free_user))
        assert api_client.post('/star-item/', {'bill_id': '1'}).status_code == 403

    def test_missing_fields(self, api_client, free_user):
        api_client.force_login(free_user)
        assert api_client.post('/star-item/', {}).status_code == 400

    def test_csrf_enforced(self, free_user):
        from rest_framework.test import APIClient
        csrf_client = APIClient(enforce_csrf_checks=True)
        csrf_client.force_login(free_user)
        assert csrf_client.post('/star-item/', {'bill_id': '1'}).status_code == 403


class TestStaffEndpoints:
    @pytest.mark.parametrize('url', ['/api/notif/send-test/', '/api/notif/send-test-null/',
                                     '/api/notif/mass-unstar/118'])
    def test_non_staff_redirected_to_login(self, client, url, free_user):
        client.force_login(free_user)
        resp = client.get(url)
        assert resp.status_code == 302
        assert '/admin/login/' in resp['Location']

    def test_mass_unstar(self, client):
        staff = make_user()
        staff.is_staff = True
        staff.save()
        profile = client.user.userprofile
        StarredBill.objects.create(user_profile=profile, bill_id='11840001')
        StarredBill.objects.create(user_profile=profile, bill_id='11940001')
        client.force_login(staff)
        resp = client.get('/api/notif/mass-unstar/118')
        assert resp.json()['deleted_count'] == 1
        assert list(StarredBill.objects.values_list('bill_id', flat=True)) == ['11940001']
