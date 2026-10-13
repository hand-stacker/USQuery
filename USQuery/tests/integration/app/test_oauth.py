"""Google / Apple sign-in (mobile JWT endpoints).

Google verification is patched at _verify_google_id_token. Apple tokens are
real RS256 JWTs signed with a throwaway key, so audience/issuer/expiry checks
in jwt.decode actually run; only the JWKS fetch is patched.
"""

from unittest import mock

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth.models import User
from django.test import override_settings

from app.api import views as api_views
from app.api.views import _find_or_create_oauth_user
from app.models import EmailVerification, UserProfile
from tests.factories import make_apple_identity_token, make_user

pytestmark = pytest.mark.django_db

GOOGLE = UserProfile.OAuthProvider.GOOGLE
APPLE = UserProfile.OAuthProvider.APPLE


class TestFindOrCreate:
    def test_existing_link(self):
        user = make_user(email='linked@example.com', oauth_provider=GOOGLE, oauth_provider_id='g-1')
        found, is_new = _find_or_create_oauth_user(GOOGLE, 'g-1', 'other@example.com')
        assert (found, is_new) == (user, False)

    def test_links_by_email(self):
        user = make_user(email='me@example.com')
        found, is_new = _find_or_create_oauth_user(GOOGLE, 'g-2', 'me@example.com')
        assert (found, is_new) == (user, False)
        profile = UserProfile.objects.get(user=user)
        assert (profile.oauth_provider, profile.oauth_provider_id) == (GOOGLE, 'g-2')

    def test_linking_activates_and_clears_pending_verification(self):
        user = make_user(email='me@example.com', active=False)
        EmailVerification.objects.create(user=user)
        _find_or_create_oauth_user(APPLE, 'a-1', 'me@example.com')
        user.refresh_from_db()
        assert user.is_active
        assert not EmailVerification.objects.filter(user=user).exists()

    def test_creates_new_user(self):
        user, is_new = _find_or_create_oauth_user(APPLE, 'a-9', 'fresh@example.com')
        assert is_new
        assert user.is_active and user.username == 'fresh@example.com'
        profile = UserProfile.objects.get(user=user)
        assert (profile.user_type, profile.oauth_provider, profile.oauth_provider_id) == (0, APPLE, 'a-9')

    def test_links_email_user_without_profile(self):
        # Accounts created before sign-up made profiles still lack one.
        User.objects.create_user(username='me@example.com', email='me@example.com', password='x')
        user, is_new = _find_or_create_oauth_user(GOOGLE, 'g-3', 'me@example.com')
        assert not is_new
        profile = UserProfile.objects.get(user=user)
        assert (profile.oauth_provider, profile.oauth_provider_id, profile.user_type) == (GOOGLE, 'g-3', 0)


class TestGoogleEndpoint:
    URL = '/api/auth/oauth/google/'

    def _post(self, api_client, payload=None, error=None):
        with mock.patch.object(api_views, '_verify_google_id_token',
                               side_effect=error, return_value=payload):
            return api_client.post(self.URL, {'id_token': 'tok'})

    def test_new_user(self, api_client):
        resp = self._post(api_client, {'sub': 'g-1', 'email': 'New@Gmail.com', 'email_verified': True})
        assert resp.status_code == 200
        assert resp.data['is_new_user'] is True
        assert resp.data['email'] == 'new@gmail.com'
        assert resp.data['access'] and resp.data['refresh']

    def test_returning_user(self, api_client):
        make_user(email='me@gmail.com', oauth_provider=GOOGLE, oauth_provider_id='g-1')
        resp = self._post(api_client, {'sub': 'g-1', 'email': 'me@gmail.com', 'email_verified': True})
        assert resp.status_code == 200 and resp.data['is_new_user'] is False

    def test_invalid_token(self, api_client):
        assert self._post(api_client, error=ValueError('bad aud')).status_code == 400

    def test_missing_email(self, api_client):
        assert self._post(api_client, {'sub': 'g-1'}).status_code == 400

    @pytest.mark.parametrize('verified', [False, 'false', None])
    def test_unverified_email_cannot_link_existing_account(self, api_client, verified):
        victim = make_user(email='victim@example.com')
        payload = {'sub': 'attacker', 'email': 'victim@example.com'}
        if verified is not None:
            payload['email_verified'] = verified
        assert self._post(api_client, payload).status_code == 400
        assert UserProfile.objects.get(user=victim).oauth_provider_id is None

    def test_string_true_accepted(self, api_client):
        resp = self._post(api_client, {'sub': 'g-1', 'email': 'me@gmail.com', 'email_verified': 'true'})
        assert resp.status_code == 200

    def test_missing_token_field(self, api_client):
        assert api_client.post(self.URL, {}).status_code == 400

    @override_settings(GOOGLE_CLIENT_IDS=None, GOOGLE_CLIENT_ID=None)
    def test_unconfigured(self, api_client):
        resp = api_client.post(self.URL, {'id_token': 'tok'})
        assert resp.status_code == 400
        assert 'not configured' in resp.data['detail']

    @override_settings(GOOGLE_CLIENT_IDS=' a , b ,', GOOGLE_CLIENT_ID='single')
    def test_client_id_list_parsing(self):
        assert api_views._get_google_allowed_client_ids() == ['a', 'b']

    @override_settings(GOOGLE_CLIENT_IDS='', GOOGLE_CLIENT_ID='single')
    def test_client_id_fallback(self):
        assert api_views._get_google_allowed_client_ids() == ['single']


@pytest.fixture(scope='module')
def apple_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


_apple_token = make_apple_identity_token


class TestAppleEndpoint:
    URL = '/api/auth/oauth/apple/'

    @pytest.fixture(autouse=True)
    def jwks(self, apple_key):
        with mock.patch.object(api_views, '_get_apple_public_key',
                               side_effect=lambda kid: apple_key.public_key() if kid == 'kid-1' else None):
            yield

    def test_first_sign_in_with_email_claim(self, api_client, apple_key):
        token = _apple_token(apple_key, email='Me@PrivateRelay.AppleID.com')
        resp = api_client.post(self.URL, {'identity_token': token})
        assert resp.status_code == 200
        assert resp.data['is_new_user'] is True
        assert resp.data['email'] == 'me@privaterelay.appleid.com'

    def test_bundle_id_audience_accepted(self, api_client, apple_key):
        token = _apple_token(apple_key, aud='com.usquery.mycongress', email='me@example.com')
        assert api_client.post(self.URL, {'identity_token': token}).status_code == 200

    def test_client_supplied_email_fallback(self, api_client, apple_key):
        token = _apple_token(apple_key)
        resp = api_client.post(self.URL, {'identity_token': token, 'email': 'cached@example.com'})
        assert resp.status_code == 200 and resp.data['email'] == 'cached@example.com'

    def test_no_email_anywhere(self, api_client, apple_key):
        assert api_client.post(self.URL, {'identity_token': _apple_token(apple_key)}).status_code == 400

    def test_expired(self, api_client, apple_key):
        token = _apple_token(apple_key, expires_in=-60, email='me@example.com')
        resp = api_client.post(self.URL, {'identity_token': token})
        assert resp.status_code == 400 and 'expired' in resp.data['detail']

    def test_wrong_audience(self, api_client, apple_key):
        token = _apple_token(apple_key, aud='com.attacker.app', email='me@example.com')
        assert api_client.post(self.URL, {'identity_token': token}).status_code == 400

    def test_wrong_signing_key(self, api_client):
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = _apple_token(other, email='me@example.com')
        assert api_client.post(self.URL, {'identity_token': token}).status_code == 400

    def test_unknown_kid(self, api_client, apple_key):
        token = _apple_token(apple_key, kid='rotated', email='me@example.com')
        assert api_client.post(self.URL, {'identity_token': token}).status_code == 400

    def test_garbage_token(self, api_client):
        assert api_client.post(self.URL, {'identity_token': 'not-a-jwt'}).status_code == 400

    @override_settings(APPLE_CLIENT_ID=None)
    def test_unconfigured(self, api_client, apple_key):
        resp = api_client.post(self.URL, {'identity_token': _apple_token(apple_key)})
        assert resp.status_code == 503
