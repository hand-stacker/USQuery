"""Mobile auth endpoints under /api/auth/ (app/api/views.py)."""

import datetime
import uuid

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from freezegun import freeze_time

from app.models import EmailVerification, UserProfile
from tests.factories import make_user

pytestmark = pytest.mark.django_db

PASSWORD = 'Str0ng-Passw0rd!'


@pytest.fixture
def pending_user(api_client, mailoutbox):
    resp = api_client.post('/api/auth/register/', {'email': 'new@example.com', 'password': PASSWORD})
    assert resp.status_code == 201
    mailoutbox.clear()
    return User.objects.get(email='new@example.com')


class TestRegister:
    def test_creates_inactive_user_and_sends_code(self, api_client, mailoutbox):
        resp = api_client.post('/api/auth/register/', {'email': 'New@Example.com', 'password': PASSWORD})
        assert resp.status_code == 201
        assert resp.data == {'status': 'success', 'email': 'new@example.com'}
        user = User.objects.get(email='new@example.com')
        assert user.username == 'new@example.com'
        assert not user.is_active
        assert user.check_password(PASSWORD)
        code = EmailVerification.objects.get(user=user).code
        assert len(mailoutbox) == 1
        assert str(code) in mailoutbox[0].body
        assert mailoutbox[0].to == ['new@example.com']

    def test_duplicate_email(self, api_client):
        make_user(email='taken@example.com')
        resp = api_client.post('/api/auth/register/', {'email': 'taken@example.com', 'password': PASSWORD})
        assert resp.status_code == 400

    def test_creates_profile(self, api_client):
        api_client.post('/api/auth/register/', {'email': 'new@example.com', 'password': PASSWORD})
        assert UserProfile.objects.filter(user__email='new@example.com', user_type=0).exists()

    def test_duplicate_email_case_insensitive(self, api_client):
        make_user(email='taken@example.com')
        resp = api_client.post('/api/auth/register/', {'email': 'Taken@Example.com', 'password': PASSWORD})
        assert resp.status_code == 400

    @pytest.mark.parametrize('password', ['short', '12345678901', 'password123'])
    def test_weak_password(self, api_client, password):
        resp = api_client.post('/api/auth/register/', {'email': 'a@example.com', 'password': password})
        assert resp.status_code == 400
        assert not User.objects.filter(email='a@example.com').exists()

    def test_invalid_email(self, api_client):
        assert api_client.post('/api/auth/register/', {'email': 'nope', 'password': PASSWORD}).status_code == 400


class TestVerifyEmail:
    def _verify(self, api_client, email, code):
        return api_client.post('/api/auth/verify-email/', {'email': email, 'code': str(code)})

    def test_valid_code_activates(self, api_client, pending_user):
        code = pending_user.emailverification.code
        resp = self._verify(api_client, 'NEW@example.com', code)
        assert resp.status_code == 200
        pending_user.refresh_from_db()
        assert pending_user.is_active
        assert not EmailVerification.objects.filter(user=pending_user).exists()

    def test_wrong_code(self, api_client, pending_user):
        assert self._verify(api_client, 'new@example.com', uuid.uuid4()).status_code == 400
        pending_user.refresh_from_db()
        assert not pending_user.is_active

    def test_expired_code(self, api_client, pending_user):
        code = pending_user.emailverification.code
        with freeze_time(timezone.now() + datetime.timedelta(minutes=11)):
            assert self._verify(api_client, 'new@example.com', code).status_code == 400

    def test_unknown_email(self, api_client):
        assert self._verify(api_client, 'ghost@example.com', uuid.uuid4()).status_code == 404


class TestResendVerification:
    def test_sends_new_code(self, api_client, pending_user, mailoutbox):
        old = pending_user.emailverification.code
        resp = api_client.post('/api/auth/resend-verification/', {'email': 'new@example.com'})
        assert resp.status_code == 200
        new = EmailVerification.objects.get(user=pending_user).code
        assert new != old
        assert len(mailoutbox) == 1 and str(new) in mailoutbox[0].body

    def test_already_active(self, api_client, free_user):
        EmailVerification.objects.create(user=free_user)
        resp = api_client.post('/api/auth/resend-verification/', {'email': free_user.email})
        assert resp.status_code == 400

    def test_daily_limit(self, api_client, pending_user):
        for _ in range(EmailVerification.MAX_DAILY_RESENDS):
            assert api_client.post('/api/auth/resend-verification/', {'email': 'new@example.com'}).status_code == 200
        resp = api_client.post('/api/auth/resend-verification/', {'email': 'new@example.com'})
        assert resp.status_code == 429


class TestLogin:
    def test_success_by_email(self, api_client):
        user = make_user(email='me@example.com', password=PASSWORD)
        resp = api_client.post('/api/auth/login/', {'email': 'ME@example.com', 'password': PASSWORD})
        assert resp.status_code == 200
        assert resp.data['user_id'] == user.id
        assert resp.data['is_verified'] is True
        assert resp.data['access'] and resp.data['refresh']

    def test_falls_back_to_email_when_username_differs(self, api_client):
        user = make_user(email='me@example.com', password=PASSWORD)
        User.objects.filter(pk=user.pk).update(username='legacy-name')
        resp = api_client.post('/api/auth/login/', {'email': 'me@example.com', 'password': PASSWORD})
        assert resp.status_code == 200

    def test_unverified_user_gets_tokens_flagged(self, api_client):
        make_user(email='me@example.com', password=PASSWORD, active=False)
        resp = api_client.post('/api/auth/login/', {'email': 'me@example.com', 'password': PASSWORD})
        assert resp.status_code == 200
        assert resp.data['is_verified'] is False

    def test_case_variant_duplicates_resolved_by_password(self, api_client):
        # Legacy data can hold Foo@x.com and foo@x.com as separate accounts.
        first = make_user(email='Dup@example.com', password='first-Passw0rd!')
        User.objects.filter(pk=first.pk).update(username='Dup@example.com')
        second = make_user(email='dup@example.com', password=PASSWORD)
        resp = api_client.post('/api/auth/login/', {'email': 'DUP@example.com', 'password': PASSWORD})
        assert resp.status_code == 200 and resp.data['user_id'] == second.id

    @pytest.mark.parametrize('email, password', [
        ('me@example.com', 'wrong'), ('ghost@example.com', PASSWORD),
    ])
    def test_bad_credentials(self, api_client, email, password):
        make_user(email='me@example.com', password=PASSWORD)
        assert api_client.post('/api/auth/login/', {'email': email, 'password': password}).status_code == 401


class TestPasswordReset:
    def test_unknown_email_same_response(self, api_client, mailoutbox):
        resp = api_client.post('/api/auth/password-reset-api/', {'email': 'ghost@example.com'})
        assert resp.status_code == 200
        assert mailoutbox == []

    def test_known_email_sends_link(self, api_client, mailoutbox):
        make_user(email='me@example.com')
        resp = api_client.post('/api/auth/password-reset-api/', {'email': 'me@example.com'})
        assert resp.status_code == 200
        assert len(mailoutbox) == 1
        assert '/api/auth/reset/' in mailoutbox[0].body
        assert 'https://' in mailoutbox[0].body


class TestAppVersion:
    def test_unset(self, api_client):
        assert api_client.get('/api/auth/app-version/').status_code == 404

    def test_set(self, api_client):
        cache.set('app_version', '2.3.1')
        resp = api_client.get('/api/auth/app-version/')
        assert resp.status_code == 200
        assert resp.data == {'version': '2.3.1'}


class TestJwtTokens:
    def test_obtain_and_refresh(self, api_client):
        make_user(email='me@example.com', password=PASSWORD)
        resp = api_client.post('/api/auth/token/', {'username': 'me@example.com', 'password': PASSWORD})
        assert resp.status_code == 200
        refreshed = api_client.post('/api/auth/token/refresh/', {'refresh': resp.data['refresh']})
        assert refreshed.status_code == 200

    def test_blacklisted_refresh_rejected(self, api_client):
        make_user(email='me@example.com', password=PASSWORD)
        tokens = api_client.post('/api/auth/token/', {'username': 'me@example.com', 'password': PASSWORD}).data
        assert api_client.post('/api/auth/token/blacklist/', {'refresh': tokens['refresh']}).status_code == 200
        assert api_client.post('/api/auth/token/refresh/', {'refresh': tokens['refresh']}).status_code == 401
