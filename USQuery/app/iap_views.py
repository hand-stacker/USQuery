"""HTTP endpoints for Apple In-App Purchase (StoreKit 2).

Two endpoints, deliberately kept out of subscription_views.py (which is large
and entirely Stripe):

- api_apple_verify        POST /api/subscription/apple/verify/
  JWT-authenticated. The app calls this on purchase, on restore, and on every
  StoreKit redelivery. It is what binds an Apple subscription to an account.

- apple_notifications     POST /api/subscription/apple/notifications/
  Unauthenticated -- the JWS signature is the authentication. Renewals,
  cancellations, refunds and expirations never touch the app, so without this
  the entitlement drifts out of sync with what the user is actually paying for.

All the state logic lives in app/apple_iap.py; these are thin HTTP wrappers.
"""

import json
import logging
import traceback

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from app import apple_iap
from app.models import AppleNotification, AppleSubscription, UserProfile
from app.subscription_views import TIER_NAMES

logger = logging.getLogger(__name__)

# Notification types whose payload fully describes the new state. They all go
# through the same reducer -- see the module docstring in apple_iap.py.
STATE_NOTIFICATIONS = {
    'SUBSCRIBED',
    'DID_RENEW',
    'DID_CHANGE_RENEWAL_PREF',
    'DID_CHANGE_RENEWAL_STATUS',
    'OFFER_REDEEMED',
    'RENEWAL_EXTENDED',
    'PRICE_INCREASE',
    'REFUND_REVERSED',
    'METADATA_UPDATE',
    'MIGRATION',
    'PRICE_CHANGE',
}

# Terminal types: the user loses access.
REVOKE_NOTIFICATIONS = {
    'EXPIRED',
    'GRACE_PERIOD_EXPIRED',
    'REFUND',
    'REVOKE',
}


def _status_payload(profile, extra=None):
    """The subscription fields the client reads back after a successful verify.

    Key names match api_subscription_status so the app can reuse one parser.
    """
    pending = profile.subscription_change_at_period_end
    payload = {
        'tier': profile.user_type,
        'tier_name': TIER_NAMES.get(profile.user_type, 'Free'),
        'period_end': (
            profile.subscription_period_end.isoformat()
            if profile.subscription_period_end else None
        ),
        'cancel_at_period_end': profile.subscription_cancel_at_period_end,
        'change_at_period_end': pending if pending != -1 else None,
        'change_at_period_end_name': TIER_NAMES.get(pending) if pending != -1 else None,
        'billing_provider': profile.billing_provider,
    }
    if extra:
        payload.update(extra)
    return payload


# Mobile REST endpoint: JWT authenticated, verifies a StoreKit signed transaction
# and grants the corresponding tier. The client keeps the transaction unfinished
# until this returns ok, so every failure path must return a non-ok body.
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_apple_verify(request):
    if not getattr(settings, 'SUBSCRIPTIONS_ENABLED', True):
        return Response({'error': 'Subscriptions are temporarily unavailable.'}, status=503)

    jws = request.data.get('jws') or request.data.get('signedTransaction') or ''
    # Sent by the client for correlation only; the signed payload is the only
    # thing we trust for product id and transaction id.
    claimed_transaction_id = request.data.get('transaction_id')
    claimed_product_id = request.data.get('product_id')

    if not jws:
        return Response({'error': 'Missing signed transaction.'}, status=400)

    try:
        transaction = apple_iap.verify_transaction(jws)
    except apple_iap.AppleVerificationError as exc:
        logger.warning('Apple verify failed for user %s: %s', request.user.id, exc)
        return Response({'error': 'Signature verification failed'}, status=400)

    if transaction.bundleId != getattr(settings, 'APPLE_IAP_BUNDLE_ID', None):
        logger.warning('Apple verify: unexpected bundle id %s', transaction.bundleId)
        return Response({'error': 'Transaction is not for this app.'}, status=400)

    environment = transaction.rawEnvironment
    if environment == 'Sandbox' and not apple_iap.sandbox_allowed():
        logger.warning('Rejected sandbox transaction %s for user %s',
                       transaction.transactionId, request.user.id)
        return Response({'error': 'Sandbox transactions are not accepted.'}, status=400)

    tier = apple_iap.tier_for_product(transaction.productId)
    if tier is None:
        logger.error('Apple verify: unknown product id %s', transaction.productId)
        return Response({'error': 'Unknown product.'}, status=400)

    if claimed_product_id and claimed_product_id != transaction.productId:
        logger.warning('Apple verify: client claimed product %s but signed payload says %s',
                       claimed_product_id, transaction.productId)
    if claimed_transaction_id and claimed_transaction_id != transaction.transactionId:
        logger.warning('Apple verify: client claimed transaction %s but signed payload says %s',
                       claimed_transaction_id, transaction.transactionId)

    original_transaction_id = transaction.originalTransactionId
    if not original_transaction_id:
        return Response({'error': 'Transaction is missing an original transaction id.'}, status=400)

    # One Apple ID must not be able to farm entitlements onto many accounts.
    existing = AppleSubscription.objects.filter(
        original_transaction_id=original_transaction_id
    ).first()
    if existing and existing.user_id != request.user.id:
        logger.warning(
            'Apple verify: transaction %s already bound to user %s, rejected for user %s',
            original_transaction_id, existing.user_id, request.user.id,
        )
        return Response(
            {'error': 'This subscription is already linked to another account.'},
            status=409,
        )

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Refuse to stack an Apple subscription on top of a live Stripe one -- the
    # user would be billed twice and only one of them could be cancelled here.
    if (
        profile.stripe_subscription_id
        and profile.billing_provider == UserProfile.BillingProvider.STRIPE
        and not profile.subscription_cancel_at_period_end
    ):
        logger.warning('Apple verify blocked: user %s has a live Stripe subscription',
                       request.user.id)
        return Response({
            'error': 'You already have a subscription billed through our website.',
            'detail': 'Cancel it at usquery.com before subscribing through the App Store.',
            'billing_provider': UserProfile.BillingProvider.STRIPE.value,
        }, status=409)

    # Prefer Apple's own view of the subscription over the single transaction the
    # client happened to hand us: it reflects renewals and cancellations the app
    # never saw. Fall back to the signed transaction if the API is unreachable so
    # a transient Apple outage can't block a paying user.
    state = apple_iap.fetch_subscription_state(
        original_transaction_id, apple_iap.environment_from_value(environment)
    )
    if state is None:
        try:
            state = apple_iap.derive_state(transaction)
        except apple_iap.AppleVerificationError as exc:
            logger.error('Apple verify: could not derive state: %s', exc)
            return Response({'error': 'Could not read the subscription state.'}, status=400)

    try:
        apple_iap.apply_state(request.user, state)
    except Exception as exc:
        logger.error('Apple verify: failed to apply state for user %s: %s',
                     request.user.id, exc, exc_info=True)
        return Response({'error': 'Could not record the subscription.'}, status=500)

    profile.refresh_from_db()
    return Response(
        _status_payload(profile, {'ok': True, 'verified': True}),
        status=200,
    )


@csrf_exempt
@require_POST
def apple_notifications(request):
    """App Store Server Notifications V2.

    Returns 200 for anything with a valid signature, including handler failures,
    so Apple stops retrying (the error is recorded on the AppleNotification row
    and in the logs instead). Only an unverifiable payload gets a 400 -- that one
    is not ours and should not be acknowledged.
    """
    try:
        body = json.loads(request.body.decode('utf-8'))
        signed_payload = body.get('signedPayload', '')
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(status=400)

    try:
        payload = apple_iap.verify_notification(signed_payload)
    except apple_iap.AppleVerificationError as exc:
        logger.warning('Apple notification signature verification failed: %s', exc)
        return HttpResponse(status=400)

    notification_type = payload.rawNotificationType or ''
    subtype = payload.rawSubtype or ''
    data = payload.data
    environment_value = (data.rawEnvironment if data else None) or ''

    if environment_value == 'Sandbox' and not apple_iap.sandbox_allowed():
        logger.info('Ignoring sandbox notification %s (%s)',
                    payload.notificationUUID, notification_type)
        return HttpResponse(status=200)

    original_transaction_id = None
    transaction = None
    renewal_info = None
    if data and data.signedTransactionInfo:
        try:
            environment = apple_iap.environment_from_value(environment_value)
            transaction = apple_iap._verifier(environment).verify_and_decode_signed_transaction(
                data.signedTransactionInfo
            )
            renewal_info = apple_iap.verify_renewal_info(data.signedRenewalInfo, environment)
            original_transaction_id = transaction.originalTransactionId
        except Exception as exc:
            logger.error('Apple notification %s: could not decode transaction: %s',
                         payload.notificationUUID, exc, exc_info=True)

    # Apple retries the same notificationUUID for up to three days.
    record, created = AppleNotification.objects.get_or_create(
        notification_uuid=payload.notificationUUID or '',
        defaults={
            'notification_type': notification_type,
            'subtype': subtype,
            'original_transaction_id': original_transaction_id,
            'signed_date': apple_iap._ms_to_dt(payload.signedDate),
            'environment': environment_value,
        },
    )
    if not created and record.processed:
        logger.info('Ignoring duplicate Apple notification %s', payload.notificationUUID)
        return HttpResponse(status=200)

    try:
        _dispatch_notification(
            record, notification_type, subtype, transaction, renewal_info, data
        )
    except Exception as exc:
        record.error = traceback.format_exc()[-4000:]
        record.save(update_fields=['error'])
        logger.error('Apple notification handler error for %s (%s): %s',
                     notification_type, payload.notificationUUID, exc, exc_info=True)

    return HttpResponse(status=200)


def _dispatch_notification(record, notification_type, subtype, transaction, renewal_info, data):
    """Route one verified notification to the state reducer or a revocation."""
    if notification_type == 'TEST':
        logger.info('Received Apple TEST notification %s', record.notification_uuid)
        _mark_processed(record)
        return

    if transaction is None:
        # Notifications without transaction data (RENEWAL_EXTENSION summaries,
        # EXTERNAL_PURCHASE_TOKEN, CONSUMPTION_REQUEST) carry nothing we act on.
        logger.info('Apple notification %s (%s) has no transaction data; recorded only',
                    notification_type, record.notification_uuid)
        _mark_processed(record)
        return

    subscription = AppleSubscription.objects.filter(
        original_transaction_id=transaction.originalTransactionId
    ).select_related('user').first()

    if subscription is None:
        # The purchase happened but verify never landed, so we don't know whose
        # account this is. Leave the row unprocessed as an audit trail; the
        # verify endpoint reconciles against the Server API when it arrives.
        logger.warning(
            'Apple notification %s (%s) for unknown subscription %s; awaiting verify',
            notification_type, record.notification_uuid, transaction.originalTransactionId,
        )
        return

    user = subscription.user

    if notification_type in REVOKE_NOTIFICATIONS:
        state = _safe_derive(transaction, renewal_info)
        apple_iap.revoke(user, state, reason=f'{notification_type}/{subtype or "-"}')
        _mark_processed(record)
        return

    if notification_type == 'DID_FAIL_TO_RENEW':
        # Billing retry or grace period: the user keeps access. EXPIRED or
        # GRACE_PERIOD_EXPIRED follows if the charge never clears.
        logger.info('Apple billing retry for user %s (subtype %s); keeping tier %s',
                    user.id, subtype or '-', subscription.tier)
        _mark_processed(record)
        return

    if notification_type in STATE_NOTIFICATIONS:
        state = apple_iap.derive_state(transaction, renewal_info)
        apple_iap.apply_state(user, state)
        _mark_processed(record)
        return

    logger.info('Unhandled Apple notification type %s (%s) for user %s',
                notification_type, subtype or '-', user.id)
    _mark_processed(record)


def _safe_derive(transaction, renewal_info):
    """derive_state that tolerates a retired/unknown product id.

    Revocation paths must still work for a product we no longer sell, so fall
    back to the identifiers alone rather than raising.
    """
    try:
        return apple_iap.derive_state(transaction, renewal_info)
    except apple_iap.AppleVerificationError:
        return {
            'original_transaction_id': transaction.originalTransactionId,
            'period_end': apple_iap._ms_to_dt(transaction.expiresDate),
        }


def _mark_processed(record):
    record.processed = True
    record.save(update_fields=['processed'])
