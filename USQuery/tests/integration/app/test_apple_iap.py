"""Tests for the Apple In-App Purchase state logic.

Signature verification is Apple's library's job and needs real signing keys, so
it is patched out here. What is tested is everything we wrote: the reducer that
turns Apple payloads into profile state, the idempotency and ordering guards,
and the account-binding rules.

Run with (needs the test-db container, see pytest.ini):
    pytest tests/integration/app/test_apple_iap.py
"""

import datetime
import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from app import apple_iap
from app.models import AppleNotification, AppleSubscription, UserProfile

PLUS = 'com.usquery.mycongress.plus.monthly'
PLUS_PRO = 'com.usquery.mycongress.pluspro.monthly'
PREMIUM = 'com.usquery.mycongress.premium.monthly'

BUNDLE_ID = 'com.usquery.mycongress'


def _ms(dt):
    return int(dt.timestamp() * 1000)


def _auth(user):
    """Bearer header for a user.

    The mobile endpoints declare authentication_classes([JWTAuthentication]),
    which replaces the defaults -- a session login is not enough.
    """
    return {'HTTP_AUTHORIZATION': f'Bearer {RefreshToken.for_user(user).access_token}'}


class FakeTransaction:
    """Stands in for JWSTransactionDecodedPayload."""

    def __init__(self, product_id=PLUS, original_transaction_id='2000000912345678',
                 transaction_id='2000000999999999', expires_date=None, signed_date=None,
                 environment='Production', revocation_date=None, app_account_token=None):
        now = timezone.now()
        self.productId = product_id
        self.originalTransactionId = original_transaction_id
        self.transactionId = transaction_id
        self.bundleId = BUNDLE_ID
        self.expiresDate = _ms(expires_date or (now + datetime.timedelta(days=30)))
        self.signedDate = _ms(signed_date or now)
        self.rawEnvironment = environment
        self.revocationDate = _ms(revocation_date) if revocation_date else None
        self.appAccountToken = app_account_token


class FakeRenewalInfo:
    """Stands in for JWSRenewalInfoDecodedPayload."""

    def __init__(self, auto_renew_status=1, auto_renew_product_id=None):
        self.rawAutoRenewStatus = auto_renew_status
        self.autoRenewProductId = auto_renew_product_id


class DeriveStateTests(TestCase):
    """The reducer is the single place that decides what Apple's payloads mean."""

    def test_active_subscription_grants_tier_with_no_pending_change(self):
        state = apple_iap.derive_state(FakeTransaction(PLUS), FakeRenewalInfo())

        self.assertEqual(state['tier'], 1)
        self.assertFalse(state['cancel_at_period_end'])
        self.assertEqual(state['change_at_period_end'], -1)

    def test_premium_maps_to_tier_two(self):
        state = apple_iap.derive_state(FakeTransaction(PREMIUM), FakeRenewalInfo())
        self.assertEqual(state['tier'], 2)

    def test_plus_pro_maps_to_tier_four(self):
        state = apple_iap.derive_state(FakeTransaction(PLUS_PRO), FakeRenewalInfo())
        self.assertEqual(state['tier'], 4)

    def test_auto_renew_off_records_pending_drop_to_free(self):
        # A cancellation supersedes any pending downgrade: 0 means "will be Free",
        # matching the convention the Stripe handlers use.
        state = apple_iap.derive_state(
            FakeTransaction(PREMIUM), FakeRenewalInfo(auto_renew_status=0)
        )

        self.assertEqual(state['tier'], 2, 'keeps the tier until the period ends')
        self.assertTrue(state['cancel_at_period_end'])
        self.assertEqual(state['change_at_period_end'], 0)

    def test_pending_downgrade_is_recorded_without_changing_current_tier(self):
        state = apple_iap.derive_state(
            FakeTransaction(PREMIUM),
            FakeRenewalInfo(auto_renew_product_id=PLUS),
        )

        self.assertEqual(state['tier'], 2)
        self.assertFalse(state['cancel_at_period_end'])
        self.assertEqual(state['change_at_period_end'], 1)

    def test_reverted_downgrade_clears_the_pending_change(self):
        state = apple_iap.derive_state(
            FakeTransaction(PREMIUM),
            FakeRenewalInfo(auto_renew_product_id=PREMIUM),
        )
        self.assertEqual(state['change_at_period_end'], -1)

    def test_unknown_auto_renew_product_is_not_guessed_at(self):
        state = apple_iap.derive_state(
            FakeTransaction(PREMIUM),
            FakeRenewalInfo(auto_renew_product_id='com.usquery.mycongress.retired'),
        )
        self.assertEqual(state['change_at_period_end'], -1)

    def test_unknown_product_is_rejected(self):
        with self.assertRaises(apple_iap.AppleVerificationError):
            apple_iap.derive_state(FakeTransaction('com.someone.else.plan'), FakeRenewalInfo())

    def test_missing_renewal_info_defaults_to_renewing(self):
        state = apple_iap.derive_state(FakeTransaction(PLUS))

        self.assertTrue(state['auto_renew_status'])
        self.assertEqual(state['change_at_period_end'], -1)


class ApplyStateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('buyer', 'buyer@example.com', 'pw')
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_applying_state_grants_the_tier_and_stamps_the_provider(self):
        state = apple_iap.derive_state(FakeTransaction(PLUS), FakeRenewalInfo())
        applied = apple_iap.apply_state(self.user, state)

        self.profile.refresh_from_db()
        self.assertTrue(applied)
        self.assertEqual(self.profile.user_type, 1)
        self.assertEqual(self.profile.billing_provider, UserProfile.BillingProvider.APPLE)
        self.assertEqual(self.profile.apple_original_transaction_id, '2000000912345678')
        self.assertIsNotNone(self.profile.subscription_period_end)

        subscription = AppleSubscription.objects.get(original_transaction_id='2000000912345678')
        self.assertEqual(subscription.user, self.user)
        self.assertEqual(subscription.tier, 1)

    def test_older_payload_does_not_overwrite_newer_state(self):
        now = timezone.now()
        newer = apple_iap.derive_state(
            FakeTransaction(PREMIUM, signed_date=now), FakeRenewalInfo()
        )
        apple_iap.apply_state(self.user, newer)

        older = apple_iap.derive_state(
            FakeTransaction(PLUS, signed_date=now - datetime.timedelta(hours=1)),
            FakeRenewalInfo(),
        )
        applied = apple_iap.apply_state(self.user, older)

        self.profile.refresh_from_db()
        self.assertFalse(applied)
        self.assertEqual(self.profile.user_type, 2, 'stale payload must not downgrade the user')

    def test_expired_payload_does_not_grant_a_tier(self):
        past = timezone.now() - datetime.timedelta(days=1)
        state = apple_iap.derive_state(
            FakeTransaction(PREMIUM, expires_date=past), FakeRenewalInfo()
        )
        apple_iap.apply_state(self.user, state)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.user_type, 0)

    def test_revoked_transaction_drops_to_free(self):
        apple_iap.apply_state(
            self.user, apple_iap.derive_state(FakeTransaction(PREMIUM), FakeRenewalInfo())
        )

        state = apple_iap.derive_state(
            FakeTransaction(PREMIUM, revocation_date=timezone.now()), FakeRenewalInfo()
        )
        apple_iap.apply_state(self.user, state)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.user_type, 0)
        self.assertEqual(self.profile.subscription_change_at_period_end, -1)
        self.assertFalse(self.profile.subscription_cancel_at_period_end)
        self.assertIsNotNone(
            AppleSubscription.objects.get(original_transaction_id='2000000912345678').revoked_at
        )

    def test_revoke_does_not_touch_a_profile_that_moved_to_stripe(self):
        apple_iap.apply_state(
            self.user, apple_iap.derive_state(FakeTransaction(PLUS), FakeRenewalInfo())
        )
        self.profile.refresh_from_db()
        self.profile.billing_provider = UserProfile.BillingProvider.STRIPE
        self.profile.user_type = 2
        self.profile.save(update_fields=['billing_provider', 'user_type'])

        apple_iap.revoke(
            self.user, {'original_transaction_id': '2000000912345678'}, reason='EXPIRED'
        )

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.user_type, 2, 'a late Apple expiry must not drop a Stripe sub')


class AppleManagedGuardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('guarded', 'guarded@example.com', 'pw')
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_live_apple_subscription_is_detected(self):
        self.profile.billing_provider = UserProfile.BillingProvider.APPLE
        self.profile.apple_original_transaction_id = '2000000912345678'
        self.profile.subscription_period_end = timezone.now() + datetime.timedelta(days=5)
        self.profile.save()

        self.assertTrue(apple_iap.apple_subscription_is_live(self.profile))

    def test_expired_apple_subscription_is_not_live(self):
        self.profile.billing_provider = UserProfile.BillingProvider.APPLE
        self.profile.apple_original_transaction_id = '2000000912345678'
        self.profile.subscription_period_end = timezone.now() - datetime.timedelta(days=1)
        self.profile.save()

        self.assertFalse(apple_iap.apple_subscription_is_live(self.profile))

    def test_stripe_subscription_is_not_apple_managed(self):
        self.profile.billing_provider = UserProfile.BillingProvider.STRIPE
        self.profile.subscription_period_end = timezone.now() + datetime.timedelta(days=5)
        self.profile.save()

        self.assertFalse(apple_iap.apple_subscription_is_live(self.profile))


@override_settings(SUBSCRIPTIONS_ENABLED=True, APPLE_IAP_BUNDLE_ID=BUNDLE_ID)
class VerifyEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', 'pw')
        UserProfile.objects.get_or_create(user=self.user)
        self.other = User.objects.create_user('mallory', 'mallory@example.com', 'pw')
        UserProfile.objects.get_or_create(user=self.other)
        self.url = reverse('api_apple_verify')

    def _post(self, user, transaction):
        with mock.patch.object(apple_iap, 'verify_transaction', return_value=transaction), \
             mock.patch.object(apple_iap, 'fetch_subscription_state', return_value=None):
            return self.client.post(
                self.url,
                data=json.dumps({
                    'jws': 'signed.jws.payload',
                    'transaction_id': transaction.transactionId,
                    'product_id': transaction.productId,
                }),
                content_type='application/json',
                **_auth(user),
            )

    def test_successful_verify_grants_the_tier(self):
        response = self._post(self.user, FakeTransaction(PLUS))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(response.json()['tier'], 1)
        self.assertEqual(response.json()['tier_name'], 'Plus')
        self.assertEqual(UserProfile.objects.get(user=self.user).user_type, 1)

    def test_transaction_bound_to_another_account_is_rejected(self):
        self._post(self.user, FakeTransaction(PLUS))
        response = self._post(self.other, FakeTransaction(PLUS))

        self.assertEqual(response.status_code, 409)
        self.assertNotIn('ok', response.json())
        self.assertEqual(UserProfile.objects.get(user=self.other).user_type, 0)

    def test_bad_signature_returns_a_non_ok_body(self):
        with mock.patch.object(
            apple_iap, 'verify_transaction',
            side_effect=apple_iap.AppleVerificationError('bad chain'),
        ):
            response = self.client.post(
                self.url,
                data=json.dumps({'jws': 'tampered'}),
                content_type='application/json',
                **_auth(self.user),
            )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn('ok', response.json())
        self.assertEqual(UserProfile.objects.get(user=self.user).user_type, 0)

    @override_settings(APPLE_IAP_ALLOW_SANDBOX=False)
    def test_sandbox_transaction_is_rejected_when_disabled(self):
        response = self._post(self.user, FakeTransaction(PLUS, environment='Sandbox'))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(UserProfile.objects.get(user=self.user).user_type, 0)

    @override_settings(APPLE_IAP_ALLOW_SANDBOX=True)
    def test_sandbox_transaction_is_accepted_when_enabled(self):
        response = self._post(self.user, FakeTransaction(PLUS, environment='Sandbox'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserProfile.objects.get(user=self.user).user_type, 1)

    def test_wrong_bundle_id_is_rejected(self):
        transaction = FakeTransaction(PLUS)
        transaction.bundleId = 'com.attacker.app'
        response = self._post(self.user, transaction)

        self.assertEqual(response.status_code, 400)

    def test_live_stripe_subscription_blocks_an_apple_purchase(self):
        profile = UserProfile.objects.get(user=self.user)
        profile.billing_provider = UserProfile.BillingProvider.STRIPE
        profile.stripe_subscription_id = 'sub_123'
        profile.save()

        response = self._post(self.user, FakeTransaction(PLUS))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['billing_provider'], 'stripe')


@override_settings(APPLE_IAP_BUNDLE_ID=BUNDLE_ID)
class NotificationEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('bob', 'bob@example.com', 'pw')
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.url = reverse('apple_notifications')
        apple_iap.apply_state(
            self.user, apple_iap.derive_state(FakeTransaction(PLUS), FakeRenewalInfo())
        )
        self.profile.refresh_from_db()

    def _notify(self, notification_type, transaction, renewal_info=None,
                subtype='', notification_uuid='uuid-1'):
        payload = mock.Mock()
        payload.rawNotificationType = notification_type
        payload.rawSubtype = subtype
        payload.notificationUUID = notification_uuid
        payload.signedDate = _ms(timezone.now())
        payload.data = mock.Mock(
            rawEnvironment='Production',
            signedTransactionInfo='signed.transaction',
            signedRenewalInfo='signed.renewal',
        )

        verifier = mock.Mock()
        verifier.verify_and_decode_signed_transaction.return_value = transaction
        with mock.patch.object(apple_iap, 'verify_notification', return_value=payload), \
             mock.patch.object(apple_iap, '_verifier', return_value=verifier), \
             mock.patch.object(apple_iap, 'verify_renewal_info', return_value=renewal_info):
            return self.client.post(
                self.url,
                data=json.dumps({'signedPayload': 'signed.notification'}),
                content_type='application/json',
            )

    def test_did_renew_extends_the_period(self):
        new_end = timezone.now() + datetime.timedelta(days=60)
        response = self._notify(
            'DID_RENEW', FakeTransaction(PLUS, expires_date=new_end), FakeRenewalInfo()
        )

        self.profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.profile.user_type, 1)
        self.assertGreater(self.profile.subscription_period_end, timezone.now() + datetime.timedelta(days=50))

    def test_auto_renew_disabled_marks_pending_cancellation(self):
        self._notify(
            'DID_CHANGE_RENEWAL_STATUS', FakeTransaction(PLUS),
            FakeRenewalInfo(auto_renew_status=0), subtype='AUTO_RENEW_DISABLED',
        )

        self.profile.refresh_from_db()
        self.assertTrue(self.profile.subscription_cancel_at_period_end)
        self.assertEqual(self.profile.subscription_change_at_period_end, 0)
        self.assertEqual(self.profile.user_type, 1, 'access is kept until the period ends')

    def test_upgrade_applies_immediately(self):
        self._notify(
            'DID_CHANGE_RENEWAL_PREF', FakeTransaction(PREMIUM),
            FakeRenewalInfo(), subtype='UPGRADE',
        )

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.user_type, 2)

    def test_downgrade_is_deferred_to_the_period_end(self):
        self._notify(
            'DID_CHANGE_RENEWAL_PREF', FakeTransaction(PLUS_PRO),
            FakeRenewalInfo(auto_renew_product_id=PLUS), subtype='DOWNGRADE',
        )

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.user_type, 4, 'keeps the higher tier until renewal')
        self.assertEqual(self.profile.subscription_change_at_period_end, 1)

    def test_expired_drops_to_free(self):
        self._notify('EXPIRED', FakeTransaction(PLUS), FakeRenewalInfo(), subtype='VOLUNTARY')

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.user_type, 0)
        self.assertIsNone(self.profile.subscription_period_end)

    def test_refund_drops_to_free_immediately(self):
        self._notify('REFUND', FakeTransaction(PLUS), FakeRenewalInfo())

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.user_type, 0)

    def test_billing_retry_keeps_access(self):
        self._notify(
            'DID_FAIL_TO_RENEW', FakeTransaction(PLUS), FakeRenewalInfo(), subtype='GRACE_PERIOD'
        )

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.user_type, 1)

    def test_duplicate_notification_is_applied_once(self):
        upgrade = FakeTransaction(PREMIUM)
        self._notify('DID_CHANGE_RENEWAL_PREF', upgrade, FakeRenewalInfo(),
                     notification_uuid='uuid-dup')

        # Apple retries the same notificationUUID for up to three days. Between
        # the two deliveries the user downgrades; the retry must not undo it.
        self.profile.refresh_from_db()
        self.profile.user_type = 1
        self.profile.save(update_fields=['user_type'])

        self._notify('DID_CHANGE_RENEWAL_PREF', upgrade, FakeRenewalInfo(),
                     notification_uuid='uuid-dup')

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.user_type, 1)
        self.assertEqual(AppleNotification.objects.filter(notification_uuid='uuid-dup').count(), 1)

    def test_notification_for_unknown_subscription_is_recorded_but_unprocessed(self):
        response = self._notify(
            'DID_RENEW',
            FakeTransaction(PLUS, original_transaction_id='9999999999'),
            FakeRenewalInfo(),
            notification_uuid='uuid-orphan',
        )

        self.assertEqual(response.status_code, 200)
        record = AppleNotification.objects.get(notification_uuid='uuid-orphan')
        self.assertFalse(record.processed, 'left for the verify endpoint to reconcile')

    def test_bad_signature_returns_400(self):
        with mock.patch.object(
            apple_iap, 'verify_notification',
            side_effect=apple_iap.AppleVerificationError('bad chain'),
        ):
            response = self.client.post(
                self.url,
                data=json.dumps({'signedPayload': 'tampered'}),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 400)


@override_settings(APPLE_IAP_BUNDLE_ID=BUNDLE_ID)
class StripeEndpointGuardTests(TestCase):
    """Stripe endpoints must refuse to act on an App Store subscription."""

    def setUp(self):
        self.user = User.objects.create_user('carol', 'carol@example.com', 'pw')
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.billing_provider = UserProfile.BillingProvider.APPLE
        self.profile.apple_original_transaction_id = '2000000912345678'
        self.profile.user_type = 1
        self.profile.subscription_period_end = timezone.now() + datetime.timedelta(days=10)
        self.profile.save()
        self.auth = _auth(self.user)

    def test_cancel_is_refused(self):
        response = self.client.post(reverse('api_cancel_subscription'), **self.auth)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['manage_url'], apple_iap.APPLE_MANAGE_URL)

    def test_billing_portal_is_refused(self):
        response = self.client.post(reverse('api_billing_portal'), **self.auth)
        self.assertEqual(response.status_code, 409)

    @override_settings(SUBSCRIPTIONS_ENABLED=True)
    def test_checkout_is_refused(self):
        # The guard runs before the tier is parsed, so this holds regardless of
        # how the Stripe price ids happen to be configured.
        response = self.client.post(
            reverse('api_create_checkout_session'),
            data=json.dumps({'tier': 2}),
            content_type='application/json',
            **self.auth,
        )
        self.assertEqual(response.status_code, 409)

    @override_settings(SUBSCRIPTIONS_ENABLED=True)
    def test_preview_is_refused(self):
        response = self.client.post(
            reverse('api_preview_subscription_change'),
            data=json.dumps({'tier': 2}),
            content_type='application/json',
            **self.auth,
        )
        self.assertEqual(response.status_code, 409)

    def test_status_reports_the_provider_and_manage_url(self):
        response = self.client.get(reverse('api_subscription_status'), **self.auth)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['billing_provider'], 'apple')
        self.assertEqual(response.json()['manage_url'], apple_iap.APPLE_MANAGE_URL)
