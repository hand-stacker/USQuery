import datetime
import logging
import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from notifications.models import UserProfile

logger = logging.getLogger(__name__)

TIER_PRICE_MAP = {
    1: getattr(settings, 'STRIPE_PLUS_PRICE_ID', None),
    2: getattr(settings, 'STRIPE_PREMIUM_PRICE_ID', None),
}

TIER_NAMES = {0: 'Free', 1: 'Plus', 2: 'Premium', 3: 'Special'}


def _stripe_client():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _get_or_create_stripe_customer(user_profile, user):
    _stripe_client()
    if user_profile.stripe_customer_id:
        return user_profile.stripe_customer_id
    customer = stripe.Customer.create(
        email=user.email,
        metadata={'user_id': user.id},
    )
    user_profile.stripe_customer_id = customer.id
    user_profile.save(update_fields=['stripe_customer_id'])
    return customer.id


@require_GET
def plans(request):
    user_tier = None
    cancel_at_period_end = False
    period_end = None
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            user_tier = profile.user_type
            cancel_at_period_end = profile.subscription_cancel_at_period_end
            period_end = profile.subscription_period_end
        except UserProfile.DoesNotExist:
            user_tier = 0

    return render(request, 'app/plans.html', {
        'title': 'Plans & Pricing',
        'user_tier': user_tier,
        'cancel_at_period_end': cancel_at_period_end,
        'period_end': period_end,
        'plus_price': getattr(settings, 'STRIPE_PLUS_DISPLAY_PRICE', '$2.99/mo'),
        'premium_price': getattr(settings, 'STRIPE_PREMIUM_DISPLAY_PRICE', '$14.99/mo'),
        'stripe_configured': bool(getattr(settings, 'STRIPE_SECRET_KEY', None)),
        'subscriptions_enabled': getattr(settings, 'SUBSCRIPTIONS_ENABLED', True),
    })


@login_required
@require_POST
def create_checkout_session(request):
    if not getattr(settings, 'SUBSCRIPTIONS_ENABLED', True):
        messages.error(request, 'Subscriptions are temporarily unavailable.')
        return redirect('plans')

    tier_str = request.POST.get('tier', '')
    try:
        tier = int(tier_str)
    except (ValueError, TypeError):
        messages.error(request, 'Invalid plan selected.')
        return redirect('plans')

    if tier not in TIER_PRICE_MAP:
        messages.error(request, 'Invalid plan selected.')
        return redirect('plans')

    price_id = TIER_PRICE_MAP[tier]
    if not price_id:
        messages.error(request, 'Payment is not configured yet. Please check back soon.')
        return redirect('plans')

    _stripe_client()
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Existing subscriber: modify the subscription instead of opening a new checkout
    if user_profile.stripe_subscription_id:
        return _modify_subscription(request, user_profile, tier, price_id)

    # New subscriber: open Stripe Checkout
    customer_id = _get_or_create_stripe_customer(user_profile, request.user)
    success_url = request.build_absolute_uri('/subscription/success/')
    cancel_url = request.build_absolute_uri('/plans/')

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode='subscription',
            line_items=[{'price': price_id, 'quantity': 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={'user_id': str(request.user.id), 'tier': str(tier)},
        )
    except stripe.error.StripeError as exc:
        logger.error('Stripe checkout session creation failed: %s', exc)
        messages.error(request, 'Payment provider error. Please try again.')
        return redirect('plans')

    return redirect(session.url, permanent=False)


def _modify_subscription(request, user_profile, new_tier, new_price_id):
    """Upgrade an existing Stripe subscription to a different price."""
    try:
        sub = stripe.Subscription.retrieve(user_profile.stripe_subscription_id)
        items_data = getattr(getattr(sub, 'items', None), 'data', [])
        if not items_data:
            raise ValueError('Subscription has no items')
        item_id = getattr(items_data[0], 'id', None)
        if not item_id:
            raise ValueError('Subscription item has no ID')

        is_upgrade = new_tier > user_profile.user_type
        stripe.Subscription.modify(
            user_profile.stripe_subscription_id,
            items=[{'id': item_id, 'price': new_price_id}],
            proration_behavior='create_prorations' if is_upgrade else 'none',
        )
    except stripe.error.StripeError as exc:
        logger.error('Stripe subscription modify failed: %s', exc)
        messages.error(request, 'Could not update your subscription. Please try again.')
        return redirect('plans')
    except Exception as exc:
        logger.error('Subscription modify error: %s', exc, exc_info=True)
        messages.error(request, 'Something went wrong. Please try again.')
        return redirect('plans')

    if is_upgrade:
        user_profile.user_type = new_tier
        user_profile.save(update_fields=['user_type'])
        messages.success(request, f'Upgraded to {TIER_NAMES[new_tier]}!')
    else:
        messages.info(request, f'Your plan will switch to {TIER_NAMES[new_tier]} at the next billing date.')

    return redirect('manage_subscription')


@login_required
@require_GET
def checkout_success(request):
    return render(request, 'app/checkout_success.html', {
        'title': 'Payment Successful',
    })


@login_required
def manage_subscription(request):
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'app/manage_subscription.html', {
        'title': 'Manage Subscription',
        'profile': user_profile,
        'tier_name': TIER_NAMES.get(user_profile.user_type, 'Free'),
        'has_stripe': bool(user_profile.stripe_customer_id),
        'subscriptions_enabled': getattr(settings, 'SUBSCRIPTIONS_ENABLED', True),
    })


@login_required
@require_POST
def billing_portal(request):
    _stripe_client()
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if not user_profile.stripe_customer_id:
        messages.info(request, 'No billing account found. Upgrade to a paid plan first.')
        return redirect('plans')

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=user_profile.stripe_customer_id,
            return_url=request.build_absolute_uri('/subscription/manage/'),
        )
    except stripe.error.StripeError as exc:
        logger.error('Stripe billing portal error: %s', exc)
        messages.error(request, 'Unable to open billing portal. Please try again.')
        return redirect('manage_subscription')

    return redirect(portal_session.url, permanent=False)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)

    _stripe_client()

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    event_type = event['type']
    data = event['data']['object']

    try:
        if event_type == 'checkout.session.completed':
            _handle_checkout_completed(data)
        elif event_type in ('customer.subscription.created', 'customer.subscription.updated'):
            _handle_subscription_updated(data)
        elif event_type == 'customer.subscription.deleted':
            _handle_subscription_deleted(data)
    except Exception as exc:
        logger.error('Webhook handler error for %s: %s', event_type, exc, exc_info=True)

    return HttpResponse(status=200)


def _ts_to_dt(ts):
    """Convert a Unix timestamp int to an aware UTC datetime, or return None."""
    if not ts:
        return None
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)


def _handle_checkout_completed(session):
    metadata = getattr(session, 'metadata', None)
    user_id = getattr(metadata, 'user_id', None) if metadata else None
    tier_str = getattr(metadata, 'tier', None) if metadata else None
    subscription_id = getattr(session, 'subscription', None)

    if not user_id or tier_str is None:
        logger.warning('checkout.session.completed: missing metadata on session %s', getattr(session, 'id', '?'))
        return

    try:
        tier = int(tier_str)
        profile = UserProfile.objects.get(user__id=user_id)
    except (ValueError, UserProfile.DoesNotExist) as exc:
        logger.error('checkout.session.completed handler error: %s', exc)
        return

    profile.user_type = tier
    profile.stripe_subscription_id = subscription_id
    profile.subscription_cancel_at_period_end = False

    if subscription_id:
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            profile.subscription_period_end = _ts_to_dt(getattr(sub, 'current_period_end', None))
        except Exception as exc:
            logger.warning('Could not retrieve subscription period end: %s', exc)

    try:
        profile.save(update_fields=[
            'user_type', 'stripe_subscription_id',
            'subscription_cancel_at_period_end', 'subscription_period_end',
        ])
        logger.info('Updated profile %s to tier %s', profile.pk, tier)
    except Exception as exc:
        logger.error('Failed to save profile after checkout.session.completed: %s', exc, exc_info=True)


def _price_to_tier():
    return {
        getattr(settings, 'STRIPE_PLUS_PRICE_ID', None): 1,
        getattr(settings, 'STRIPE_PREMIUM_PRICE_ID', None): 2,
    }


def _handle_subscription_updated(sub):
    customer_id = getattr(sub, 'customer', None)
    if not customer_id:
        return

    try:
        profile = UserProfile.objects.get(stripe_customer_id=customer_id)
    except UserProfile.DoesNotExist:
        logger.warning('No profile found for Stripe customer %s', customer_id)
        return

    update_fields = ['subscription_cancel_at_period_end', 'subscription_period_end']

    profile.subscription_cancel_at_period_end = getattr(sub, 'cancel_at_period_end', False)
    profile.subscription_period_end = _ts_to_dt(getattr(sub, 'current_period_end', None))

    # Sync tier if the price changed (e.g. after an upgrade/downgrade modify)
    try:
        items_data = getattr(getattr(sub, 'items', None), 'data', [])
        if items_data:
            price_id = getattr(getattr(items_data[0], 'price', None), 'id', None)
            tier = _price_to_tier().get(price_id)
            if tier is not None and profile.user_type != tier:
                profile.user_type = tier
                update_fields.append('user_type')
    except Exception as exc:
        logger.warning('Could not read tier from subscription items: %s', exc)

    profile.save(update_fields=update_fields)


def _handle_subscription_deleted(sub):
    customer_id = getattr(sub, 'customer', None)
    if not customer_id:
        return

    try:
        profile = UserProfile.objects.get(stripe_customer_id=customer_id)
    except UserProfile.DoesNotExist:
        logger.warning('No profile found for Stripe customer %s', customer_id)
        return

    profile.user_type = 0
    profile.stripe_subscription_id = None
    profile.subscription_period_end = None
    profile.subscription_cancel_at_period_end = False
    profile.save(update_fields=[
        'user_type', 'stripe_subscription_id',
        'subscription_period_end', 'subscription_cancel_at_period_end',
    ])


def _modify_subscription_api(user_profile, new_tier, new_price_id):
    """Like _modify_subscription but returns a dict for API callers instead of redirecting."""
    try:
        sub = stripe.Subscription.retrieve(user_profile.stripe_subscription_id)
        items_data = getattr(getattr(sub, 'items', None), 'data', [])
        if not items_data:
            raise ValueError('Subscription has no items')
        item_id = getattr(items_data[0], 'id', None)
        if not item_id:
            raise ValueError('Subscription item has no ID')

        is_upgrade = new_tier > user_profile.user_type
        stripe.Subscription.modify(
            user_profile.stripe_subscription_id,
            items=[{'id': item_id, 'price': new_price_id}],
            proration_behavior='create_prorations' if is_upgrade else 'none',
        )
    except stripe.error.StripeError as exc:
        logger.error('Stripe subscription modify failed (mobile): %s', exc)
        return {'error': 'Could not update your subscription.', 'status_code': 502}
    except Exception as exc:
        logger.error('Subscription modify error (mobile): %s', exc, exc_info=True)
        return {'error': 'Something went wrong.', 'status_code': 500}

    if is_upgrade:
        user_profile.user_type = new_tier
        user_profile.save(update_fields=['user_type'])

    return {
        'status_code': 200,
        'modified': True,
        'is_upgrade': is_upgrade,
        'tier': new_tier,
        'tier_name': TIER_NAMES[new_tier],
        'message': (
            f'Upgraded to {TIER_NAMES[new_tier]}.'
            if is_upgrade
            else f'Your plan will switch to {TIER_NAMES[new_tier]} at the next billing date.'
        ),
    }


# Mobile REST endpoint: JWT authenticated, cancel subscription at period end
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_cancel_subscription(request):
    _stripe_client()
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if not user_profile.stripe_subscription_id:
        return Response({'error': 'No active subscription found.'}, status=404)

    if user_profile.subscription_cancel_at_period_end:
        return Response({'error': 'Subscription is already set to cancel.'}, status=409)

    try:
        stripe.Subscription.modify(
            user_profile.stripe_subscription_id,
            cancel_at_period_end=True,
        )
    except stripe.error.StripeError as exc:
        logger.error('Stripe subscription cancel failed (mobile): %s', exc)
        return Response({'error': 'Could not cancel subscription.'}, status=502)

    user_profile.subscription_cancel_at_period_end = True
    user_profile.save(update_fields=['subscription_cancel_at_period_end'])

    period_end = user_profile.subscription_period_end
    return Response({
        'cancelled': True,
        'period_end': period_end.isoformat() if period_end else None,
        'message': 'Your subscription will cancel at the end of the billing period.',
    })


# Mobile REST endpoint: JWT authenticated undo a pending cancellation
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_reactivate_subscription(request):
    _stripe_client()
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if not user_profile.stripe_subscription_id:
        return Response({'error': 'No active subscription found.'}, status=404)

    if not user_profile.subscription_cancel_at_period_end:
        return Response({'error': 'Subscription is not pending cancellation.'}, status=409)

    try:
        stripe.Subscription.modify(
            user_profile.stripe_subscription_id,
            cancel_at_period_end=False,
        )
    except stripe.error.StripeError as exc:
        logger.error('Stripe subscription reactivate failed (mobile): %s', exc)
        return Response({'error': 'Could not reactivate subscription.'}, status=502)

    user_profile.subscription_cancel_at_period_end = False
    user_profile.save(update_fields=['subscription_cancel_at_period_end'])

    return Response({
        'reactivated': True,
        'message': 'Your subscription has been reactivated and will renew normally.',
    })


# Mobile REST endpoint: public, returns all tier details for the plans screen
@api_view(['GET'])
def api_plans(request):
    plus_price = getattr(settings, 'STRIPE_PLUS_DISPLAY_PRICE', '$4.99/mo')
    premium_price = getattr(settings, 'STRIPE_PREMIUM_DISPLAY_PRICE', '$9.99/mo')
    stripe_configured = bool(getattr(settings, 'STRIPE_SECRET_KEY', None))
    return Response({
        'stripe_configured': stripe_configured,
        'subscriptions_enabled': getattr(settings, 'SUBSCRIPTIONS_ENABLED', False),
        'tiers': [
            {
                'id': 0,
                'name': 'Free',
                'price': '$0',
                'price_period': 'forever',
                'starred_members_limit': 3,
                'starred_bills_limit': 10,
                'predictions_per_day': 0,
                'chat_messages_per_day': 0,
            },
            {
                'id': 1,
                'name': 'Plus',
                'price': plus_price,
                'price_period': 'monthly',
                'starred_members_limit': 10,
                'starred_bills_limit': 50,
                'predictions_per_day': 3,
                'chat_messages_per_day': 3,
            },
            {
                'id': 2,
                'name': 'Premium',
                'price': premium_price,
                'price_period': 'monthly',
                'starred_members_limit': 100,
                'starred_bills_limit': 100,
                'predictions_per_day': None,
                'chat_messages_per_day': None,
            },
        ],
    })


# Mobile REST endpoint: JWT authenticated, returns current user's subscription status
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_subscription_status(request):
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    period_end = user_profile.subscription_period_end
    return Response({
        'tier': user_profile.user_type,
        'tier_name': TIER_NAMES.get(user_profile.user_type, 'Free'),
        'cancel_at_period_end': user_profile.subscription_cancel_at_period_end,
        'period_end': period_end.isoformat() if period_end else None,
        'starred_members_limit': user_profile.get_starred_memberships_limit(),
        'starred_bills_limit': user_profile.get_starred_bills_limit(),
    })


# Mobile REST endpoint: returns a Stripe Checkout URL for the app to open in a browser
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_create_checkout_session(request):
    if not getattr(settings, 'SUBSCRIPTIONS_ENABLED', True):
        return Response({'error': 'Subscriptions are temporarily unavailable.'}, status=503)

    tier_str = request.data.get('tier', '')
    try:
        tier = int(tier_str)
    except (ValueError, TypeError):
        return Response({'error': 'Invalid tier.'}, status=400)

    if tier not in TIER_PRICE_MAP:
        return Response({'error': 'Invalid tier.'}, status=400)

    price_id = TIER_PRICE_MAP[tier]
    if not price_id:
        return Response({'error': 'Payment not configured yet.'}, status=503)

    _stripe_client()
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if user_profile.stripe_subscription_id:
        result = _modify_subscription_api(user_profile, tier, price_id)
        status_code = result.pop('status_code', 200)
        return Response(result, status=status_code)

    customer_id = _get_or_create_stripe_customer(user_profile, request.user)

    success_url = request.build_absolute_uri('/subscription/success/')
    cancel_url = request.build_absolute_uri('/plans/')

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode='subscription',
            line_items=[{'price': price_id, 'quantity': 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={'user_id': str(request.user.id), 'tier': str(tier)},
        )
    except stripe.error.StripeError as exc:
        logger.error('Stripe checkout session creation failed (mobile): %s', exc)
        return Response({'error': 'Payment provider error.'}, status=502)

    return Response({'checkout_url': session.url}, status=200)

# Mobile REST endpoint: JWT authenticated, returns a Stripe Billing Portal URL
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_billing_portal(request):
    _stripe_client()
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if not user_profile.stripe_customer_id:
        return Response({'error': 'No billing account found. Upgrade to a paid plan first.'}, status=404)

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=user_profile.stripe_customer_id,
            return_url='https://www.usquery.com/subscription/manage/',
        )
    except stripe.error.StripeError as exc:
        logger.error('Stripe billing portal error (mobile): %s', exc)
        return Response({'error': 'Unable to open billing portal. Please try again.'}, status=502)

    return Response({'portal_url': portal_session.url})

