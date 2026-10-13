"""Session-based web account flows in app/views.py."""

import datetime
from unittest import mock

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from freezegun import freeze_time

from app import views as app_views
from app.api import views as api_views
from app.models import EmailVerification, UserProfile
from notifications.models import StarredBill, StarredMembership
from tests.factories import (
    jwt_headers, make_apple_identity_token, make_bill, make_membership, make_user,
)

pytestmark = pytest.mark.django_db

PASSWORD = 'Str0ng-Passw0rd!'


def _register(client, email='web@example.com', email2=None):
    return client.post('/register/', {'email': email, 'email2': email2 or email,
                                      'password1': PASSWORD, 'password2': PASSWORD})


class TestRegister:
    def test_page(self, client):
        assert client.get('/register/').status_code == 200

    def test_creates_inactive_user_and_emails_code(self, client, mailoutbox):
        resp = _register(client)
        assert resp.status_code == 302 and resp['Location'] == '/verify-email/web@example.com/'
        user = User.objects.get(email='web@example.com')
        assert not user.is_active and user.username == 'web@example.com'
        assert str(user.emailverification.code) in mailoutbox[0].body

    def test_mismatched_emails(self, client):
        resp = _register(client, 'a@example.com', 'b@example.com')
        assert resp.status_code == 200
        assert not User.objects.exists()

    def test_duplicate(self, client):
        make_user(email='web@example.com')
        _register(client)
        assert User.objects.filter(email='web@example.com').count() == 1

    def test_creates_profile(self, client):
        _register(client)
        assert UserProfile.objects.filter(user__email='web@example.com', user_type=0).exists()

    def test_email_stored_lowercase(self, client):
        _register(client, 'Mixed@Example.com')
        user = User.objects.get()
        assert (user.email, user.username) == ('mixed@example.com', 'mixed@example.com')

    def test_case_variant_duplicate_rejected(self, client):
        make_user(email='taken@example.com')
        _register(client, 'Taken@Example.com')
        assert User.objects.count() == 1

    def test_mixed_case_web_user_can_use_mobile_login(self, client, api_client):
        _register(client, 'Mixed@Example.com')
        User.objects.update(is_active=True)
        resp = api_client.post('/api/auth/login/', {'email': 'Mixed@Example.com', 'password': PASSWORD})
        assert resp.status_code == 200

    def test_legacy_mixed_case_account_logs_in_everywhere(self, client, api_client):
        # Accounts created before emails were lowercased keep their original case.
        make_user(email='Legacy@Example.com', password=PASSWORD)
        assert api_client.post('/api/auth/login/', {'email': 'legacy@example.com', 'password': PASSWORD}).status_code == 200
        resp = client.post('/login/', {'username': 'LEGACY@example.com', 'password': PASSWORD})
        assert resp.status_code == 302 and '_auth_user_id' in client.session


class TestVerifyEmail:
    @pytest.fixture
    def pending(self, client):
        _register(client)
        return User.objects.get(email='web@example.com')

    def test_page(self, client, pending):
        assert client.get('/verify-email/web@example.com/').status_code == 200

    def test_correct_code_activates_and_creates_profile(self, client, pending):
        resp = client.post('/verify-email/web@example.com/', {'code': str(pending.emailverification.code)})
        assert resp.status_code == 302 and resp['Location'] == '/login/'
        pending.refresh_from_db()
        assert pending.is_active
        assert UserProfile.objects.filter(user=pending, user_type=0).exists()

    def test_wrong_code(self, client, pending):
        client.post('/verify-email/web@example.com/', {'code': '00000000-0000-0000-0000-000000000000'})
        pending.refresh_from_db()
        assert not pending.is_active

    def test_expired_code(self, client, pending):
        code = str(pending.emailverification.code)
        with freeze_time(timezone.now() + datetime.timedelta(minutes=11)):
            client.post('/verify-email/web@example.com/', {'code': code})
        pending.refresh_from_db()
        assert not pending.is_active

    def test_unknown_email(self, client):
        assert client.get('/verify-email/ghost@example.com/').status_code == 404


class TestResend:
    @pytest.fixture
    def pending(self, client, mailoutbox):
        _register(client)
        mailoutbox.clear()
        return User.objects.get(email='web@example.com')

    def test_sends(self, client, pending, mailoutbox):
        resp = client.get('/verify-email/web@example.com/resend/')
        assert resp.status_code == 302
        assert len(mailoutbox) == 1

    def test_already_verified(self, client, pending):
        User.objects.filter(pk=pending.pk).update(is_active=True)
        assert client.get('/verify-email/web@example.com/resend/').status_code == 403

    def test_per_ip_throttle(self, client, pending, mailoutbox):
        cache.set('resend_ip:127.0.0.1', 5)
        client.get('/verify-email/web@example.com/resend/')
        assert mailoutbox == []

    def test_throttle_keys_on_forwarded_ip(self, client, pending, mailoutbox):
        cache.set('resend_ip:9.9.9.9', 5)
        client.get('/verify-email/web@example.com/resend/', HTTP_X_FORWARDED_FOR='9.9.9.9')
        assert mailoutbox == []
        client.get('/verify-email/web@example.com/resend/', HTTP_X_FORWARDED_FOR='8.8.8.8')
        assert len(mailoutbox) == 1


class TestLogin:
    def test_success(self, client):
        make_user(email='me@example.com', password=PASSWORD)
        resp = client.post('/login/', {'username': 'me@example.com', 'password': PASSWORD})
        assert resp.status_code == 302
        assert '_auth_user_id' in client.session

    def test_unverified_redirected_to_verification(self, client):
        make_user(email='me@example.com', password=PASSWORD, active=False)
        resp = client.post('/login/', {'username': 'me@example.com', 'password': PASSWORD})
        assert resp.status_code == 302 and resp['Location'] == '/verify-email/me@example.com/'

    def test_unverified_wrong_password_not_redirected(self, client):
        make_user(email='me@example.com', password=PASSWORD, active=False)
        resp = client.post('/login/', {'username': 'me@example.com', 'password': 'wrong'})
        assert resp.status_code == 200
        assert '_auth_user_id' not in client.session


class TestWebOAuth:
    def test_google(self, client):
        with mock.patch.object(app_views, '_verify_google_id_token',
                               return_value={'sub': 'g-1', 'email': 'G@Gmail.com', 'email_verified': True}):
            resp = client.post('/oauth/google/', {'id_token': 'tok'})
        assert resp.json() == {'detail': 'ok', 'redirect': '/'}
        assert int(client.session['_auth_user_id']) == User.objects.get(email='g@gmail.com').id

    def test_google_unverified_email_rejected(self, client):
        with mock.patch.object(app_views, '_verify_google_id_token',
                               return_value={'sub': 'g-1', 'email': 'g@gmail.com', 'email_verified': False}):
            assert client.post('/oauth/google/', {'id_token': 'tok'}).status_code == 400
        assert '_auth_user_id' not in client.session

    def test_google_invalid(self, client):
        with mock.patch.object(app_views, '_verify_google_id_token', side_effect=ValueError('bad')):
            assert client.post('/oauth/google/', {'id_token': 'tok'}).status_code == 400
        assert client.post('/oauth/google/', {}).status_code == 400
        assert client.get('/oauth/google/').status_code == 405

    def test_apple(self, client):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = make_apple_identity_token(key, email='me@example.com')
        with mock.patch.object(api_views, '_get_apple_public_key', return_value=key.public_key()):
            resp = client.post('/oauth/apple/', {'identity_token': token})
        assert resp.status_code == 200
        assert '_auth_user_id' in client.session

    def test_apple_rejects_bundle_id_audience_on_web(self, client):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = make_apple_identity_token(key, aud='com.usquery.mycongress', email='me@example.com')
        with mock.patch.object(api_views, '_get_apple_public_key', return_value=key.public_key()):
            assert client.post('/oauth/apple/', {'identity_token': token}).status_code == 400


class TestAccountDeletion:
    def test_anonymous_page(self, client):
        assert client.get('/api/auth/delete/').status_code == 200

    def test_anonymous_post_goes_to_login(self, client):
        resp = client.post('/api/auth/delete/', {'action': 'schedule'})
        assert resp['Location'] == '/login/?next=/api/auth/delete/'

    def test_schedule_and_unschedule(self, client, free_user):
        client.force_login(free_user)
        client.post('/api/auth/delete/', {'action': 'schedule'})
        assert UserProfile.objects.get(user=free_user).scheduled_for_deletion
        client.post('/api/auth/delete/', {'action': 'unschedule'})
        assert not UserProfile.objects.get(user=free_user).scheduled_for_deletion


class TestViewDetails:
    def test_jwt(self, api_client, plus_user):
        api_client.credentials(**jwt_headers(plus_user))
        resp = api_client.get('/api/auth/view-details/')
        assert resp.status_code == 202
        assert resp.data == {'user_type': 1, 'device_limit': 5, 'bill_limit': 50, 'member_limit': 10}

    def test_anonymous(self, api_client):
        assert api_client.get('/api/auth/view-details/').status_code == 401


class TestStarredPage:
    def test_anonymous(self, client):
        assert client.get('/starred/').status_code == 403

    def test_lists_active_stars(self, client, free_user):
        bill = make_bill(119, 4, 1, title='Starred Bill')
        unstarred = make_bill(119, 4, 2)
        membership = make_membership()
        profile = free_user.userprofile
        StarredBill.objects.create(user_profile=profile, bill_id=str(bill.id))
        StarredBill.objects.create(user_profile=profile, bill_id=str(unstarred.id), is_active=False)
        StarredMembership.objects.create(user_profile=profile, membership_id=membership.id)
        client.force_login(free_user)
        with mock.patch.object(app_views, 'batch_load_summaries',
                               mock.AsyncMock(return_value={bill.id: {'summary': 'Short summary'}})):
            ctx = client.get('/starred/').context
        assert [(b['bill_id'], b['summary']) for b in ctx['bills_json']] == [(bill.id, 'Short summary')]
        assert [m['membership_id'] for m in ctx['members_json']] == [membership.id]
