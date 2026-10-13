"""Apple In-App Purchase (StoreKit 2) subscription logic.

iOS cannot sell subscriptions through Stripe (App Store guideline 3.1.1), so
every iOS purchase goes through StoreKit and lands here. Stripe remains the
payment path for web and Android; the two are kept apart by
UserProfile.billing_provider.

This module is pure logic -- no views, no HTTP handling -- so the verify
endpoint, the notification webhook and the reconcile command all share it.

The design principle is that there is exactly one place that decides what the
subscription state is: derive_state(). Apple sends ~12 notification types, but
every one of them carries the same two signed objects (transaction + renewal
info), and the full profile state is a function of those two. Writing bespoke
field mutations per notification type would drift and mis-handle out-of-order
delivery; deriving the whole state and assigning it absolutely does not. This
mirrors how the Stripe handlers in subscription_views.py stay idempotent.
"""

import datetime
import logging
import threading
import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from appstoreserverlibrary.api_client import AppStoreServerAPIClient, APIException
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.models.Status import Status
from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier, VerificationException

from app.models import AppleSubscription, UserProfile

logger = logging.getLogger(__name__)

# Product ids must match IOS_SKU_BY_TIER in the mobile app's constants/iap.ts
# exactly, and the subscription-group level ordering in App Store Connect must
# match TIER_RANKS in subscription_views.py (Plus < Plus Pro < Premium) so
# StoreKit treats the moves as the upgrades/downgrades we expect.
APPLE_PRODUCT_TO_TIER = {
    'com.usquery.mycongress.plus.monthly': 1,
    'com.usquery.mycongress.pluspro.monthly': 4,
    'com.usquery.mycongress.premium.monthly': 2,
}

# Where iOS users manage or cancel an App Store subscription. There is no
# server-side cancel API for Apple subscriptions -- this URL is the only answer.
APPLE_MANAGE_URL = 'https://apps.apple.com/account/subscriptions'

APPLE_ROOT_CA_DIR = Path(__file__).resolve().parent / 'certs'

# Subscription statuses that still entitle the user to their tier. Billing retry
# and grace period both keep access while Apple retries the charge; EXPIRED and
# REVOKED do not.
ENTITLED_STATUSES = (Status.ACTIVE, Status.BILLING_RETRY, Status.BILLING_GRACE_PERIOD)


class AppleVerificationError(Exception):
    """Raised when a signed payload cannot be verified or is not ours."""


_cache_lock = threading.Lock()
_root_certificates = None
_verifiers = {}
_api_clients = {}


def _load_root_certificates():
    """Read the Apple root CA DER bytes used to anchor the x5c chain."""
    global _root_certificates
    if _root_certificates is None:
        certs = []
        for path in sorted(APPLE_ROOT_CA_DIR.glob('*.cer')):
            certs.append(path.read_bytes())
        if not certs:
            raise AppleVerificationError(
                f'No Apple root certificates found in {APPLE_ROOT_CA_DIR}. '
                'Download AppleRootCA-G3.cer from https://www.apple.com/certificateauthority/'
            )
        _root_certificates = certs
    return _root_certificates


def _verifier(environment: Environment) -> SignedDataVerifier:
    """Build (and cache) a SignedDataVerifier for one environment.

    A verifier is bound to a single environment and rejects payloads from the
    other, which is exactly the isolation we want -- see verify_transaction for
    how the correct one is chosen.
    """
    with _cache_lock:
        verifier = _verifiers.get(environment)
        if verifier is not None:
            return verifier

        bundle_id = getattr(settings, 'APPLE_IAP_BUNDLE_ID', None)
        if not bundle_id:
            raise AppleVerificationError('APPLE_IAP_BUNDLE_ID is not configured.')

        app_apple_id = getattr(settings, 'APPLE_IAP_APP_APPLE_ID', None)
        # The library requires appAppleId for Production and forbids relying on
        # it for Sandbox (sandbox notifications omit the field).
        if environment == Environment.PRODUCTION:
            if not app_apple_id:
                raise AppleVerificationError(
                    'APPLE_IAP_APP_APPLE_ID is required to verify production transactions.'
                )
            app_apple_id = int(app_apple_id)
        else:
            app_apple_id = None

        verifier = SignedDataVerifier(
            _load_root_certificates(),
            True,  # enable_online_checks: OCSP-check the signing certificates
            environment,
            bundle_id,
            app_apple_id,
        )
        _verifiers[environment] = verifier
        return verifier


def sandbox_allowed() -> bool:
    return bool(getattr(settings, 'APPLE_IAP_ALLOW_SANDBOX', False))


def _environments():
    """Environments to attempt verification against, production first."""
    envs = [Environment.PRODUCTION]
    if sandbox_allowed():
        envs.append(Environment.SANDBOX)
    return envs


def _verify_with_fallback(signed_data: str, method_name: str):
    """Verify against production, then sandbox if that is enabled.

    The payload carries its own `environment` claim, but reading it before
    verification would mean trusting unverified input to pick the verifier.
    Trying each verifier in turn keeps the signature check authoritative: a
    payload only ever succeeds against the verifier for its real environment.
    """
    last_error = None
    for environment in _environments():
        try:
            return getattr(_verifier(environment), method_name)(signed_data)
        except VerificationException as exc:
            last_error = exc
        except AppleVerificationError:
            raise
        except Exception as exc:
            last_error = exc
            logger.warning('Apple %s failed for %s: %s', method_name, environment, exc)

    raise AppleVerificationError(f'Signature verification failed: {last_error}')


def verify_transaction(jws: str):
    """Verify a StoreKit 2 signed transaction; returns the decoded payload."""
    if not jws:
        raise AppleVerificationError('Missing signed transaction.')
    return _verify_with_fallback(jws, 'verify_and_decode_signed_transaction')


def verify_notification(signed_payload: str):
    """Verify an App Store Server Notification V2; returns the decoded payload."""
    if not signed_payload:
        raise AppleVerificationError('Missing signedPayload.')
    return _verify_with_fallback(signed_payload, 'verify_and_decode_notification')


def verify_renewal_info(signed_renewal_info: str, environment: Environment):
    """Verify a signed renewal info blob for a known environment.

    Unlike transactions this is only ever called once the environment is already
    established by the enclosing notification or transaction, so there is no
    fallback -- a mismatch here is a real error.
    """
    if not signed_renewal_info:
        return None
    try:
        return _verifier(environment).verify_and_decode_renewal_info(signed_renewal_info)
    except VerificationException as exc:
        raise AppleVerificationError(f'Renewal info verification failed: {exc}')


def _api_client(environment: Environment):
    """Build (and cache) an App Store Server API client, or None if unconfigured.

    The Server API is optional: everything works from the signed payloads alone,
    it just makes restore and reconciliation authoritative rather than
    best-effort. Callers must handle None.
    """
    with _cache_lock:
        if environment in _api_clients:
            return _api_clients[environment]

        key_id = getattr(settings, 'APPLE_IAP_KEY_ID', None)
        issuer_id = getattr(settings, 'APPLE_IAP_ISSUER_ID', None)
        bundle_id = getattr(settings, 'APPLE_IAP_BUNDLE_ID', None)
        signing_key = _load_signing_key()

        if not (key_id and issuer_id and bundle_id and signing_key):
            _api_clients[environment] = None
            return None

        client = AppStoreServerAPIClient(signing_key, key_id, issuer_id, bundle_id, environment)
        _api_clients[environment] = client
        return client


def _load_signing_key():
    """Return the .p8 private key bytes from the inline PEM or the file path."""
    inline = getattr(settings, 'APPLE_IAP_PRIVATE_KEY', None)
    if inline and inline.strip():
        return inline.strip().encode('utf-8')

    path = getattr(settings, 'APPLE_IAP_PRIVATE_KEY_PATH', None)
    if path:
        try:
            return Path(path).read_bytes()
        except OSError as exc:
            logger.error('Could not read APPLE_IAP_PRIVATE_KEY_PATH %s: %s', path, exc)
    return None


def _ms_to_dt(ms):
    """Convert Apple's epoch milliseconds to an aware UTC datetime, or None.

    Note Apple uses milliseconds where Stripe uses seconds -- this is
    deliberately separate from subscription_views._ts_to_dt.
    """
    if not ms:
        return None
    return datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc)


def tier_for_product(product_id):
    return APPLE_PRODUCT_TO_TIER.get(product_id)


def environment_from_value(value):
    """Coerce Apple's environment string ('Sandbox'/'Production') to the enum."""
    try:
        return Environment(value)
    except ValueError:
        return Environment.PRODUCTION


def _as_uuid(value):
    """appAccountToken arrives as a string; ignore anything that isn't a UUID."""
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def derive_state(transaction, renewal_info=None, status=None):
    """Reduce a signed transaction (+ renewal info) to the profile state it implies.

    Returns a dict consumed by apply_state. This is the single place that
    decides what a set of Apple payloads means, so every notification type, the
    verify endpoint and the reconcile command all agree.

    change_at_period_end follows the convention documented on
    UserProfile.subscription_change_at_period_end and implemented for Stripe in
    subscription_views._handle_subscription_updated: -1 means no pending change,
    and 0 doubles as "will drop to Free", since a pending cancellation
    supersedes any pending downgrade.
    """
    tier = tier_for_product(transaction.productId)
    if tier is None:
        raise AppleVerificationError(f'Unknown product id: {transaction.productId}')

    auto_renew_on = True
    auto_renew_product_id = transaction.productId
    if renewal_info is not None:
        if renewal_info.rawAutoRenewStatus is not None:
            auto_renew_on = renewal_info.rawAutoRenewStatus == 1
        auto_renew_product_id = renewal_info.autoRenewProductId or transaction.productId

    if not auto_renew_on:
        # Cancelled: keeps the tier until expiry, then drops to Free.
        change_at_period_end = 0
    else:
        pending_tier = tier_for_product(auto_renew_product_id)
        # An unrecognized autoRenewProductId (e.g. a plan we retired) is not
        # something we can map to a tier, so treat it as no pending change
        # rather than guessing.
        change_at_period_end = pending_tier if pending_tier is not None and pending_tier != tier else -1

    return {
        'original_transaction_id': transaction.originalTransactionId,
        'latest_transaction_id': transaction.transactionId,
        'product_id': transaction.productId,
        'tier': tier,
        'environment': transaction.rawEnvironment or Environment.PRODUCTION.value,
        'period_end': _ms_to_dt(transaction.expiresDate),
        'cancel_at_period_end': not auto_renew_on,
        'change_at_period_end': change_at_period_end,
        'auto_renew_status': auto_renew_on,
        'auto_renew_product_id': auto_renew_product_id,
        'app_account_token': _as_uuid(transaction.appAccountToken),
        'signed_date': _ms_to_dt(transaction.signedDate),
        'revoked': bool(transaction.revocationDate) or status == Status.REVOKED,
        'status': status,
    }


def fetch_subscription_state(original_transaction_id, environment):
    """Ask Apple for the authoritative current state of a subscription.

    Returns a derive_state dict, or None when the Server API is unconfigured or
    unreachable -- callers fall back to the payload they already hold rather
    than failing a paying user over a transient Apple outage.
    """
    client = _api_client(environment)
    if client is None:
        return None

    try:
        response = client.get_all_subscription_statuses(original_transaction_id)
    except (APIException, Exception) as exc:  # noqa: B014 - APIException named for clarity
        logger.warning(
            'App Store Server API lookup failed for %s: %s', original_transaction_id, exc
        )
        return None

    for group in response.data or []:
        for item in group.lastTransactions or []:
            if item.originalTransactionId != original_transaction_id:
                continue
            try:
                transaction = _verifier(environment).verify_and_decode_signed_transaction(
                    item.signedTransactionInfo
                )
                renewal_info = verify_renewal_info(item.signedRenewalInfo, environment)
            except (VerificationException, AppleVerificationError) as exc:
                logger.warning('Could not verify Server API payload for %s: %s',
                               original_transaction_id, exc)
                return None
            return derive_state(transaction, renewal_info, status=item.status)

    logger.warning('App Store Server API returned no transaction for %s', original_transaction_id)
    return None


def _is_expired(state):
    """Whether the subscription's paid period has already elapsed."""
    period_end = state.get('period_end')
    return bool(period_end and period_end <= timezone.now())


def apply_state(user, state):
    """Write the derived state to AppleSubscription and UserProfile atomically.

    Returns True if applied, False if skipped because the payload is older than
    what we already have. Apple does not guarantee delivery order, so a retried
    or delayed notification must never overwrite newer state.
    """
    if state.get('revoked'):
        return revoke(user, state, reason='revoked')

    signed_date = state.get('signed_date')

    with db_transaction.atomic():
        profile = (
            UserProfile.objects.select_for_update()
            .filter(user=user)
            .first()
        )
        if profile is None:
            profile = UserProfile.objects.create(user=user)

        subscription, _ = AppleSubscription.objects.select_for_update().get_or_create(
            original_transaction_id=state['original_transaction_id'],
            defaults={
                'user': user,
                'product_id': state['product_id'],
                'environment': state['environment'],
            },
        )

        if (
            signed_date
            and subscription.last_signed_date
            and signed_date < subscription.last_signed_date
        ):
            logger.info(
                'Skipping out-of-order Apple payload for %s (signed %s < stored %s)',
                state['original_transaction_id'], signed_date, subscription.last_signed_date,
            )
            return False

        subscription.user = user
        subscription.product_id = state['product_id']
        subscription.tier = state['tier']
        subscription.environment = state['environment']
        subscription.latest_transaction_id = state.get('latest_transaction_id')
        subscription.expires_date = state.get('period_end')
        subscription.auto_renew_status = state['auto_renew_status']
        subscription.auto_renew_product_id = state.get('auto_renew_product_id')
        subscription.app_account_token = state.get('app_account_token')
        subscription.revoked_at = None
        subscription.last_signed_date = signed_date or subscription.last_signed_date
        subscription.save()

        # A payload for an already-elapsed period (a late EXPIRED-adjacent
        # notification, or reconciliation of a long-dead subscription) must not
        # re-grant the tier.
        if _is_expired(state) and state.get('status') not in ENTITLED_STATUSES:
            _clear_profile_subscription(profile)
            return True

        profile.user_type = state['tier']
        profile.billing_provider = UserProfile.BillingProvider.APPLE
        profile.apple_original_transaction_id = state['original_transaction_id']
        profile.subscription_period_end = state.get('period_end')
        profile.subscription_cancel_at_period_end = state['cancel_at_period_end']
        profile.subscription_change_at_period_end = state['change_at_period_end']
        profile.save(update_fields=[
            'user_type', 'billing_provider', 'apple_original_transaction_id',
            'subscription_period_end', 'subscription_cancel_at_period_end',
            'subscription_change_at_period_end',
        ])

    logger.info(
        'Applied Apple subscription state for user %s: tier %s, ends %s, cancel=%s, pending=%s',
        user.id, state['tier'], state.get('period_end'),
        state['cancel_at_period_end'], state['change_at_period_end'],
    )
    return True


def _clear_profile_subscription(profile):
    """Drop the profile to Free, clearing every subscription field.

    Mirrors subscription_views._handle_subscription_deleted so an Apple
    expiry/refund leaves exactly the same shape as a Stripe cancellation.
    """
    profile.user_type = 0
    profile.subscription_period_end = None
    profile.subscription_cancel_at_period_end = False
    profile.subscription_change_at_period_end = -1
    profile.save(update_fields=[
        'user_type', 'subscription_period_end',
        'subscription_cancel_at_period_end', 'subscription_change_at_period_end',
    ])


def revoke(user, state, reason=''):
    """Terminal drop to Free for an expiry, refund or revocation."""
    with db_transaction.atomic():
        profile = UserProfile.objects.select_for_update().filter(user=user).first()
        if profile is None:
            profile = UserProfile.objects.create(user=user)

        original_transaction_id = state.get('original_transaction_id') if state else None
        if original_transaction_id:
            AppleSubscription.objects.filter(
                original_transaction_id=original_transaction_id
            ).update(
                revoked_at=timezone.now(),
                auto_renew_status=False,
                expires_date=state.get('period_end'),
            )

        # Only clear if Apple still owns this profile's subscription. A user who
        # already moved to Stripe must not be dropped by a late Apple expiry.
        if profile.billing_provider == UserProfile.BillingProvider.APPLE:
            _clear_profile_subscription(profile)

    logger.info('Revoked Apple subscription for user %s (%s)', user.id, reason)
    return True


def apple_subscription_is_live(profile):
    """Whether this profile's subscription is currently owned by Apple.

    Used by the Stripe endpoints to refuse operations they cannot perform: an
    App Store subscription can only be cancelled or changed by the user in the
    App Store, never through our backend.
    """
    if profile.billing_provider != UserProfile.BillingProvider.APPLE:
        return False
    if not profile.apple_original_transaction_id:
        return False
    period_end = profile.subscription_period_end
    return bool(period_end and period_end > timezone.now())


def apple_managed_error():
    """The 409 body returned when a Stripe endpoint is hit for an Apple sub."""
    return {
        'error': 'This subscription is managed by the App Store.',
        'detail': 'Manage or cancel it in your Apple ID subscription settings.',
        'billing_provider': UserProfile.BillingProvider.APPLE.value,
        'manage_url': APPLE_MANAGE_URL,
    }
