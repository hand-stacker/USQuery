import datetime
import logging
import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from notifications.models import UserProfile
from app import apple_iap

logger = logging.getLogger(__name__)

TIER_PRICE_MAP = {
    1: getattr(settings, 'STRIPE_PLUS_PRICE_ID', None),
    4: getattr(settings, 'STRIPE_PLUS_PRO_PRICE_ID', None),
    2: getattr(settings, 'STRIPE_PREMIUM_PRICE_ID', None),
}

# Human-readable recurring price per tier (e.g. '$19.99/mo'), shown on confirm UIs.
TIER_DISPLAY_PRICE = {
    1: getattr(settings, 'STRIPE_PLUS_DISPLAY_PRICE', '$2.99/mo'),
    4: getattr(settings, 'STRIPE_PLUS_PRO_DISPLAY_PRICE', '$7.99/mo'),
    2: getattr(settings, 'STRIPE_PREMIUM_DISPLAY_PRICE', '$19.99/mo'),
}

TIER_NAMES = {0: 'Free', 1: 'Plus', 2: 'Premium', 3: 'Special', 4: 'Plus Pro'}

# Custom URL scheme the mobile app registers (app.json: "scheme": "usqmobileapp").
# Stripe rejects custom schemes on return/success/cancel URLs, so mobile Stripe
# sessions point at the https return_to_app view, which bounces to this scheme.
APP_SCHEME = 'usqmobileapp'

# Tier IDs are stable DB values and don't sort by plan level (Plus Pro was added
# as ID 4 between Plus and Premium). Use ranks for upgrade/downgrade comparisons.
TIER_RANKS = {0: 0, 1: 1, 4: 2, 2: 3, 3: 4}


def _is_upgrade(new_tier, current_tier) -> bool:
    return TIER_RANKS.get(new_tier, 0) > TIER_RANKS.get(current_tier, 0)


def _apple_managed_response(user_profile):
    """409 Response if this subscription belongs to the App Store, else None.

    An Apple subscription can only be changed or cancelled by the user in their
    Apple ID settings -- there is no server-side API for it -- so the Stripe
    endpoints must refuse rather than silently do nothing or double-bill.
    """
    if apple_iap.apple_subscription_is_live(user_profile):
        return Response(apple_iap.apple_managed_error(), status=409)
    return None


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
    pending_change = -1
    pending_change_name = None
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            user_tier = profile.user_type
            cancel_at_period_end = profile.subscription_cancel_at_period_end
            period_end = profile.subscription_period_end
            pending_change = profile.subscription_change_at_period_end
            if pending_change != -1:
                pending_change_name = TIER_NAMES.get(pending_change)
        except UserProfile.DoesNotExist:
            user_tier = 0

    return render(request, 'app/plans.html', {
        'title': 'Plans & Pricing',
        'user_tier': user_tier,
        'cancel_at_period_end': cancel_at_period_end,
        'period_end': period_end,
        'pending_change': pending_change,
        'pending_change_name': pending_change_name,
        'plus_price': getattr(settings, 'STRIPE_PLUS_DISPLAY_PRICE', '$2.99/mo'),
        'plus_pro_price': getattr(settings, 'STRIPE_PLUS_PRO_DISPLAY_PRICE', '$7.99/mo'),
        'premium_price': getattr(settings, 'STRIPE_PREMIUM_DISPLAY_PRICE', '$19.99/mo'),
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

    # Existing subscriber: show the prorated cost on a confirmation page first,
    # and only modify the subscription once the user confirms (confirmed=1).
    if user_profile.stripe_subscription_id:
        if tier == user_profile.user_type:
            # Re-selecting the current tier while a cancellation is pending resumes
            # the subscription (un-cancels it) so the user keeps their plan.
            if user_profile.subscription_cancel_at_period_end:
                try:
                    _reactivate_subscription(user_profile)
                except stripe.error.StripeError as exc:
                    logger.error('Stripe subscription resume failed: %s', exc)
                    messages.error(request, 'Could not resume your subscription. Please try again.')
                    return redirect('manage_subscription')
                messages.success(request, f'Your subscription was resumed. You will stay on {TIER_NAMES[user_profile.user_type]}.')
                return redirect('manage_subscription')
            # Re-selecting the current tier while a downgrade is pending cancels
            # that scheduled change so the user stays put.
            if user_profile.subscription_change_at_period_end != -1:
                _cancel_scheduled_change(user_profile)
                messages.success(request, f'Your scheduled plan change was cancelled. You will stay on {TIER_NAMES[user_profile.user_type]}.')
                return redirect('manage_subscription')
            messages.info(request, 'You are already on this plan.')
            return redirect('manage_subscription')
        if request.POST.get('confirmed') == '1':
            return _modify_subscription(request, user_profile, tier, price_id)
        return redirect(f'/subscription/confirm/?tier={tier}')

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


@login_required
@require_GET
def confirm_subscription_change(request):
    """Confirmation page shown to an existing subscriber before a tier change is
    committed (web flow). Displays the prorated immediate charge for upgrades, or
    the deferred-switch notice for downgrades, with a Confirm button that POSTs
    back to create_checkout_session with confirmed=1."""
    if not getattr(settings, 'SUBSCRIPTIONS_ENABLED', True):
        messages.error(request, 'Subscriptions are temporarily unavailable.')
        return redirect('plans')

    tier_str = request.GET.get('tier', '')
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

    # New subscribers don't confirm here -- Stripe Checkout is their confirmation.
    if not user_profile.stripe_subscription_id:
        return redirect('plans')

    preview, _status = _build_change_preview(user_profile, tier, price_id)
    if 'error' in preview:
        messages.error(request, preview['error'])
        return redirect('plans')

    return render(request, 'app/confirm_change.html', {
        'title': 'Confirm Plan Change',
        'tier': tier,
        'tier_name': TIER_NAMES.get(tier, ''),
        'preview': preview,
    })


def _phase_item_price(item):
    """Extract the price ID from a subscription schedule phase item (which may be
    a dict, a Stripe object, an id string, or an expanded price object)."""
    price = item['price'] if isinstance(item, dict) else getattr(item, 'price', None)
    if isinstance(price, str):
        return price
    return getattr(price, 'id', None)


def _schedule_downgrade(sub, new_price_id):
    """Defer a downgrade to the end of the current paid period using a Stripe
    subscription schedule.

    The current (higher) price is kept for the remainder of the already-paid
    period; the new (lower) price takes over at the next billing date. No
    proration or refund is issued -- the user keeps the higher tier they paid
    for until subscription_period_end. Returns the schedule.

    If a schedule already exists on the subscription (e.g. the user is changing
    an already-pending downgrade to a different tier), it is reused and its
    upcoming phase is rewritten to the new price.
    """
    schedule_id = getattr(sub, 'schedule', None)
    if schedule_id:
        schedule = stripe.SubscriptionSchedule.retrieve(schedule_id)
    else:
        schedule = stripe.SubscriptionSchedule.create(from_subscription=sub.id)

    # phases[0] mirrors the current subscription (current price + period dates).
    # Preserve it as-is and append the new (lower) price as the next phase, which
    # takes effect when the current phase ends (i.e. at the next billing date).
    current_phase = schedule['phases'][0]
    current_items = [
        {'price': _phase_item_price(it), 'quantity': (it['quantity'] if isinstance(it, dict) else getattr(it, 'quantity', 1)) or 1}
        for it in current_phase['items']
    ]
    return stripe.SubscriptionSchedule.modify(
        schedule.id,
        end_behavior='release',
        proration_behavior='none',
        phases=[
            {
                'items': current_items,
                'start_date': current_phase['start_date'],
                'end_date': current_phase['end_date'],
            },
            {
                'items': [{'price': new_price_id, 'quantity': 1}],
            },
        ],
    )


def _release_schedule(sub):
    """Release any subscription schedule attached to the subscription so the
    subscription becomes a plain subscription again (cancels a pending deferred
    change). No-op if there is no schedule."""
    schedule_id = getattr(sub, 'schedule', None)
    if schedule_id:
        stripe.SubscriptionSchedule.release(schedule_id)


def _cancel_scheduled_change(user_profile):
    """Cancel a pending deferred tier change: release the Stripe schedule (if any)
    and clear the local pending flag so the user stays on their current tier."""
    try:
        sub = stripe.Subscription.retrieve(user_profile.stripe_subscription_id)
        _release_schedule(sub)
    except stripe.error.StripeError as exc:
        logger.warning('Could not release scheduled change for user %s: %s', user_profile.user_id, exc)
    user_profile.subscription_change_at_period_end = -1
    user_profile.save(update_fields=['subscription_change_at_period_end'])


def _reactivate_subscription(user_profile):
    """Undo a pending cancellation: clear the scheduled cancellation on Stripe and
    on the profile. Also clears the cancel-induced "drop to Free" marker
    (subscription_change_at_period_end == 0) so the UI stops showing a pending
    switch. Raises stripe.error.StripeError on failure.

    Clears the cancellation by unsetting `cancel_at` (empty string) -- on the dahlia
    API a pending cancel is a `cancel_at` timestamp, so that's what we remove. Do
    NOT also pass `cancel_at_period_end`; Stripe rejects both fields in one call."""
    stripe.Subscription.modify(
        user_profile.stripe_subscription_id,
        cancel_at='',
    )
    user_profile.subscription_cancel_at_period_end = False
    fields = ['subscription_cancel_at_period_end']
    if user_profile.subscription_change_at_period_end == 0:
        user_profile.subscription_change_at_period_end = -1
        fields.append('subscription_change_at_period_end')
    user_profile.save(update_fields=fields)


def _execute_tier_change(user_profile, new_tier, new_price_id):
    """Apply a tier change to an existing Stripe subscription.

    Upgrades charge the prorated difference for the rest of the current period
    immediately, keeping the existing billing date (we deliberately do NOT pass
    billing_cycle_anchor='now' -- resetting it stacked unused-time credits across
    same-period changes and over-refunded). The change is only committed if the
    card is charged successfully (payment_behavior='error_if_incomplete') --
    otherwise Stripe raises and the subscription is left on the old tier, so we
    never grant a paid tier without payment. An upgrade also releases any pending
    deferred downgrade so the higher tier applies immediately.

    Downgrades are deferred via a subscription schedule: no refund is issued, the
    higher tier (and its access) is kept until subscription_period_end, and the
    lower price takes over at the next billing date. The caller records the
    pending tier in subscription_change_at_period_end; user_type is NOT changed
    now -- the webhook flips it once the schedule's lower price becomes active.

    Returns (is_upgrade, updated_subscription). Raises stripe.error.StripeError
    or ValueError on failure.
    """
    sub = stripe.Subscription.retrieve(user_profile.stripe_subscription_id)
    items_data = getattr(getattr(sub, 'items', None), 'data', [])
    if not items_data:
        raise ValueError('Subscription has no items')
    item_id = getattr(items_data[0], 'id', None)
    if not item_id:
        raise ValueError('Subscription item has no ID')

    is_upgrade = _is_upgrade(new_tier, user_profile.user_type)
    if is_upgrade:
        # If a downgrade was scheduled, release it so the upgrade applies now and
        # the pending change is discarded (caller clears the local flag).
        try:
            _release_schedule(sub)
        except stripe.error.StripeError as exc:
            logger.warning('Could not release schedule before upgrade for user %s: %s', user_profile.user_id, exc)
        # NOTE: do NOT reset the billing cycle (billing_cycle_anchor='now').
        # Keeping the existing period means the proration is bounded to the
        # unused time *in this period* -- Stripe credits the old tier and charges
        # the new tier for the remaining days, then renews at the new price on the
        # original date. Resetting the anchor instead credited the entire unused
        # item value on every change, which stacked across multiple same-period
        # changes and produced phantom over-refunds (the plus->premium->plus->
        # premium "$39 returned" case).
        updated = stripe.Subscription.modify(
            user_profile.stripe_subscription_id,
            items=[{'id': item_id, 'price': new_price_id}],
            proration_behavior='always_invoice',
            payment_behavior='error_if_incomplete',
            cancel_at='',  # an upgrade also un-cancels a pending cancellation
        )
        return is_upgrade, updated

    # Downgrade: defer to the period end via a subscription schedule. If the sub
    # was set to cancel at period end, actively choosing a (lower) plan resumes it:
    # clear the cancellation first so the scheduled downgrade can take effect at
    # renewal instead of the subscription being cancelled before it ever activates.
    if user_profile.subscription_cancel_at_period_end:
        stripe.Subscription.modify(sub.id, cancel_at='')
        sub = stripe.Subscription.retrieve(sub.id)
    _schedule_downgrade(sub, new_price_id)
    return is_upgrade, sub


def _modify_subscription(request, user_profile, new_tier, new_price_id):
    """Change an existing Stripe subscription to a different tier (web flow)."""
    try:
        is_upgrade, updated = _execute_tier_change(user_profile, new_tier, new_price_id)
    except stripe.error.CardError as exc:
        logger.warning('Upgrade payment declined for user %s: %s', request.user.id, exc)
        messages.error(request, 'Your card could not be charged. Please update your payment method and try again.')
        return redirect('manage_subscription')
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
        user_profile.subscription_period_end = _subscription_period_end(updated)
        user_profile.subscription_cancel_at_period_end = False
        user_profile.subscription_change_at_period_end = -1
        user_profile.save(update_fields=['user_type', 'subscription_period_end', 'subscription_cancel_at_period_end', 'subscription_change_at_period_end'])
        messages.success(request, f'Upgraded to {TIER_NAMES[new_tier]}! Your card was charged the prorated difference.')
    else:
        # Deferred downgrade: keep user_type until period end; record the pending
        # tier so the UI can warn the user. The webhook applies it at rollover.
        # cancel flag is cleared in case this downgrade resumed a pending cancel.
        user_profile.subscription_change_at_period_end = new_tier
        user_profile.subscription_cancel_at_period_end = False
        user_profile.save(update_fields=['subscription_change_at_period_end', 'subscription_cancel_at_period_end'])
        messages.info(request, f'Your plan will switch to {TIER_NAMES[new_tier]} at the next billing date. You keep {TIER_NAMES[user_profile.user_type]} until then.')

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
    pending_change = user_profile.subscription_change_at_period_end
    return render(request, 'app/manage_subscription.html', {
        'title': 'Manage Subscription',
        'profile': user_profile,
        'tier_name': TIER_NAMES.get(user_profile.user_type, 'Free'),
        'pending_change_name': TIER_NAMES.get(pending_change) if pending_change != -1 else None,
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


@require_GET
def return_to_app(request):
    """Deep-link bounce for the mobile app.

    Stripe rejects custom URL schemes on return_url/success_url/cancel_url, so the
    mobile billing-portal and Checkout sessions point here (https) and we bounce to
    the app's custom scheme. The in-app auth browser
    (ASWebAuthenticationSession / Chrome Custom Tabs) watches for usqmobileapp:// and
    auto-dismisses, returning control to the app. status: success | cancel | manage.

    Kept unauthenticated -- the in-app browser has no Django session and the page
    exposes nothing sensitive (just a redirect to a fixed scheme).
    """
    status = request.GET.get('status', 'manage')
    if status not in ('success', 'cancel', 'manage'):
        status = 'manage'
    deep_link = f'{APP_SCHEME}://subscription/manage?status={status}'

    # Build the 302 manually: HttpResponseRedirect would raise DisallowedRedirect
    # for a non-http(s) scheme (its allowed_schemes is http/https/ftp). The HTML body
    # is only shown if the in-app browser blocks the automatic redirect -- it offers a
    # tappable fallback link. status is whitelisted above, so deep_link is fully
    # server-controlled (no injection); escape() is belt-and-suspenders.
    safe = escape(deep_link)
    html = (
        f'<!doctype html><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0;url={safe}">'
        f'<script>window.location.replace("{safe}");</script>'
        f'<p>Returning to the app… '
        f'<a href="{safe}">Tap here if it doesn\'t open automatically.</a></p>'
    )
    resp = HttpResponse(html, status=302)
    resp['Location'] = deep_link
    return resp


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


def _is_pending_cancellation(sub):
    """Whether the subscription is set to cancel at the end of its period.

    Two valid Stripe representations, depending on billing mode:
    - **flexible** billing mode (what we use): `cancel_at_period_end` is deprecated
      and left `False`; the cancellation is a future `cancel_at` timestamp instead
      (the billing portal and our own cancel both produce this).
    - **classic** billing mode: the legacy `cancel_at_period_end` boolean is `True`
      and `cancel_at` is null.
    Check both so detection is correct regardless of mode. In either case `status`
    stays `active`; an immediate cancellation flips `status` to `canceled` and fires
    `customer.subscription.deleted`, which is handled separately.
    """
    return bool(getattr(sub, 'cancel_at', None)) or bool(getattr(sub, 'cancel_at_period_end', False))


def _subscription_period_end(sub):
    """Return the subscription's current period end as an aware datetime.

    As of Stripe API 2026-04-22 current_period_end lives on the subscription
    item, not the subscription object, so read it from the first item.
    """
    items_data = getattr(getattr(sub, 'items', None), 'data', [])
    if not items_data:
        return None
    return _ts_to_dt(getattr(items_data[0], 'current_period_end', None))


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
    profile.billing_provider = UserProfile.BillingProvider.STRIPE
    profile.subscription_cancel_at_period_end = False
    profile.subscription_change_at_period_end = -1

    if subscription_id:
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            profile.subscription_period_end = _subscription_period_end(sub)
        except Exception as exc:
            logger.warning('Could not retrieve subscription period end: %s', exc)

    try:
        profile.save(update_fields=[
            'user_type', 'stripe_subscription_id', 'billing_provider',
            'subscription_cancel_at_period_end', 'subscription_period_end',
            'subscription_change_at_period_end',
        ])
        logger.info('Updated profile %s to tier %s', profile.pk, tier)
    except Exception as exc:
        logger.error('Failed to save profile after checkout.session.completed: %s', exc, exc_info=True)


def _price_to_tier():
    return {
        getattr(settings, 'STRIPE_PLUS_PRICE_ID', None): 1,
        getattr(settings, 'STRIPE_PLUS_PRO_PRICE_ID', None): 4,
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

    profile.subscription_cancel_at_period_end = _is_pending_cancellation(sub)
    profile.subscription_period_end = _subscription_period_end(sub)

    # Reconcile the pending-change flag against the cancel state. A cancellation
    # supersedes a pending deferred downgrade: when the period ends the user drops
    # to Free, so the old downgrade target (a paid tier) no longer applies -- record
    # the pending change as Free (0). Conversely, if the cancellation was undone
    # (e.g. resumed via the billing portal), clear that cancel-induced Free marker.
    if profile.subscription_cancel_at_period_end:
        if profile.subscription_change_at_period_end > 0:
            profile.subscription_change_at_period_end = 0
            update_fields.append('subscription_change_at_period_end')
    else:
        if profile.subscription_change_at_period_end == 0:
            profile.subscription_change_at_period_end = -1
            update_fields.append('subscription_change_at_period_end')

    # Sync tier if the price changed (e.g. after an upgrade/downgrade modify).
    # Only grant a tier when the subscription is actually active/paid so an
    # upgrade whose payment never cleared can't unlock a higher tier for free.
    try:
        sub_status = getattr(sub, 'status', None)
        items_data = getattr(getattr(sub, 'items', None), 'data', [])
        if items_data and sub_status in ('active', 'trialing'):
            price_id = getattr(getattr(items_data[0], 'price', None), 'id', None)
            tier = _price_to_tier().get(price_id)
            if tier is not None:
                if profile.user_type != tier:
                    profile.user_type = tier
                    update_fields.append('user_type')
                # A deferred downgrade has taken effect once the active price
                # matches the pending tier; clear the pending flag.
                if profile.subscription_change_at_period_end == tier:
                    profile.subscription_change_at_period_end = -1
                    update_fields.append('subscription_change_at_period_end')
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
    profile.subscription_change_at_period_end = -1
    profile.save(update_fields=[
        'user_type', 'stripe_subscription_id',
        'subscription_period_end', 'subscription_cancel_at_period_end',
        'subscription_change_at_period_end',
    ])


def _modify_subscription_api(user_profile, new_tier, new_price_id):
    """Like _modify_subscription but returns a dict for API callers instead of redirecting."""
    try:
        is_upgrade, updated = _execute_tier_change(user_profile, new_tier, new_price_id)
    except stripe.error.CardError as exc:
        logger.warning('Upgrade payment declined (mobile) for user %s: %s', user_profile.user_id, exc)
        return {
            'status_code': 402,
            'payment_failed': True,
            'error': 'Your card could not be charged. Please update your payment method and try again.',
        }
    except stripe.error.StripeError as exc:
        logger.error('Stripe subscription modify failed (mobile): %s', exc)
        return {'error': 'Could not update your subscription.', 'status_code': 502}
    except Exception as exc:
        logger.error('Subscription modify error (mobile): %s', exc, exc_info=True)
        return {'error': 'Something went wrong.', 'status_code': 500}

    if is_upgrade:
        user_profile.user_type = new_tier
        user_profile.subscription_period_end = _subscription_period_end(updated)
        user_profile.subscription_cancel_at_period_end = False
        user_profile.subscription_change_at_period_end = -1
        user_profile.save(update_fields=['user_type', 'subscription_period_end', 'subscription_cancel_at_period_end', 'subscription_change_at_period_end'])
    else:
        # Deferred downgrade: keep user_type until period end; record the pending
        # tier so the app can warn the user. The webhook applies it at rollover.
        # cancel flag is cleared in case this downgrade resumed a pending cancel.
        user_profile.subscription_change_at_period_end = new_tier
        user_profile.subscription_cancel_at_period_end = False
        user_profile.save(update_fields=['subscription_change_at_period_end', 'subscription_cancel_at_period_end'])

    return {
        'status_code': 200,
        'modified': True,
        'is_upgrade': is_upgrade,
        'tier': new_tier,
        'tier_name': TIER_NAMES[new_tier],
        'change_at_period_end': user_profile.subscription_change_at_period_end if not is_upgrade else -1,
        'message': (
            f'Upgraded to {TIER_NAMES[new_tier]}. Your card was charged the prorated difference '
            f'for the rest of this period; your billing date is unchanged.'
            if is_upgrade
            else f'Your plan will switch to {TIER_NAMES[new_tier]} at the next billing date. '
                 f'You keep {TIER_NAMES[user_profile.user_type]} until then.'
        ),
    }


# Mobile REST endpoint: JWT authenticated, cancel subscription at period end
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_cancel_subscription(request):
    _stripe_client()
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    apple_managed = _apple_managed_response(user_profile)
    if apple_managed:
        return apple_managed

    if not user_profile.stripe_subscription_id:
        return Response({'error': 'No active subscription found.'}, status=404)

    if user_profile.subscription_cancel_at_period_end:
        return Response({'error': 'Subscription is already set to cancel.'}, status=409)

    try:
        # A subscription managed by a schedule (a pending deferred downgrade) can't
        # take a cancellation -- release the schedule first so the cancel applies.
        # The pending downgrade is moot now: the user drops to Free at period end
        # regardless. In flexible billing mode cancel_at_period_end is deprecated;
        # cancel at the current period end via cancel_at='min_period_end' (Stripe's
        # recommended migration -- it resolves to the period-end timestamp).
        sub = stripe.Subscription.retrieve(user_profile.stripe_subscription_id)
        _release_schedule(sub)
        stripe.Subscription.modify(
            user_profile.stripe_subscription_id,
            cancel_at='min_period_end',
        )
    except stripe.error.StripeError as exc:
        logger.error('Stripe subscription cancel failed (mobile): %s', exc)
        return Response({'error': 'Could not cancel subscription.'}, status=502)

    user_profile.subscription_cancel_at_period_end = True
    fields = ['subscription_cancel_at_period_end']
    if user_profile.subscription_change_at_period_end > 0:
        user_profile.subscription_change_at_period_end = 0
        fields.append('subscription_change_at_period_end')
    user_profile.save(update_fields=fields)

    period_end = user_profile.subscription_period_end
    pending_change = user_profile.subscription_change_at_period_end
    return Response({
        'cancelled': True,
        'cancel_at_period_end': True,
        'period_end': period_end.isoformat() if period_end else None,
        # A pending downgrade is superseded by the cancel (the user drops to Free at
        # period end); 0 = Free, -1 = no pending change.
        'change_at_period_end': pending_change if pending_change != -1 else None,
        'change_at_period_end_name': TIER_NAMES.get(pending_change) if pending_change != -1 else None,
        'message': 'Your subscription will cancel at the end of the billing period.',
    })


# Mobile REST endpoint: JWT authenticated undo a pending cancellation
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_reactivate_subscription(request):
    _stripe_client()
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    apple_managed = _apple_managed_response(user_profile)
    if apple_managed:
        return apple_managed

    if not user_profile.stripe_subscription_id:
        return Response({'error': 'No active subscription found.'}, status=404)

    if not user_profile.subscription_cancel_at_period_end:
        return Response({'error': 'Subscription is not pending cancellation.'}, status=409)

    try:
        _reactivate_subscription(user_profile)
    except stripe.error.StripeError as exc:
        logger.error('Stripe subscription reactivate failed (mobile): %s', exc)
        return Response({'error': 'Could not reactivate subscription.'}, status=502)

    pending_change = user_profile.subscription_change_at_period_end
    return Response({
        'reactivated': True,
        'cancel_at_period_end': False,
        # The cancel-induced "drop to Free" marker is cleared on reactivate, so this
        # is normally -1/null (the user keeps their current tier).
        'change_at_period_end': pending_change if pending_change != -1 else None,
        'change_at_period_end_name': TIER_NAMES.get(pending_change) if pending_change != -1 else None,
        'message': 'Your subscription has been reactivated and will renew normally.',
    })


# Mobile REST endpoint: public, returns all tier details for the plans screen
@api_view(['GET'])
@permission_classes([AllowAny])
def api_plans(request):
    plus_price = getattr(settings, 'STRIPE_PLUS_DISPLAY_PRICE', '$2.99/mo')
    plus_pro_price = getattr(settings, 'STRIPE_PLUS_PRO_DISPLAY_PRICE', '$7.99/mo')
    premium_price = getattr(settings, 'STRIPE_PREMIUM_DISPLAY_PRICE', '$19.99/mo')
    stripe_configured = bool(getattr(settings, 'STRIPE_SECRET_KEY', None))
    # iOS buys through StoreKit, so the app needs the product id for each tier.
    # Serving it here keeps the SKU map in one place instead of hardcoded in the
    # client; tier_for_product() is the same table the verifier uses.
    apple_product_by_tier = {
        tier: product_id
        for product_id, tier in apple_iap.APPLE_PRODUCT_TO_TIER.items()
    }
    return Response({
        'stripe_configured': stripe_configured,
        'iap_configured': bool(getattr(settings, 'APPLE_IAP_BUNDLE_ID', None)),
        'subscriptions_enabled': getattr(settings, 'SUBSCRIPTIONS_ENABLED', False),
        'tiers': [
            {
                'id': 0,
                'name': 'Free',
                'price': '$0',
                'price_period': 'forever',
                'apple_product_id': None,
                'starred_members_limit': 3,
                'starred_bills_limit': 10,
                'predictions_per_day': 0,
                'chat_messages_per_day': 0,
                'chat_monthly_input_token_limit': None,
                'chat_monthly_web_search_limit': 0,
            },
            {
                'id': 1,
                'name': 'Plus',
                'price': plus_price,
                'price_period': 'monthly',
                'apple_product_id': apple_product_by_tier.get(1),
                'starred_members_limit': 10,
                'starred_bills_limit': 50,
                'predictions_per_day': 10,
                'chat_messages_per_day': 10,
                'chat_monthly_input_token_limit': None,
                'chat_monthly_web_search_limit': 30,
            },
            {
                'id': 4,
                'name': 'Plus Pro',
                'price': plus_pro_price,
                'price_period': 'monthly',
                'apple_product_id': apple_product_by_tier.get(4),
                'starred_members_limit': 25,
                'starred_bills_limit': 100,
                'predictions_per_day': 30,
                'chat_messages_per_day': 30,
                'chat_monthly_input_token_limit': None,
                'chat_monthly_web_search_limit': 60,
            },
            {
                'id': 2,
                'name': 'Premium',
                'price': premium_price,
                'price_period': 'monthly',
                'apple_product_id': apple_product_by_tier.get(2),
                'starred_members_limit': 100,
                'starred_bills_limit': 1000,
                'predictions_per_day': None,
                'chat_messages_per_day': None,
                'chat_monthly_input_token_limit': 5_000_000,
                'chat_monthly_web_search_limit': 200,
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
    pending_change = user_profile.subscription_change_at_period_end
    apple_managed = apple_iap.apple_subscription_is_live(user_profile)
    return Response({
        'tier': user_profile.user_type,
        'tier_name': TIER_NAMES.get(user_profile.user_type, 'Free'),
        # Which processor owns this subscription, so the app sends the user to the
        # right place to manage it: 'apple' -> App Store, 'stripe' -> billing
        # portal, null -> never subscribed.
        'billing_provider': user_profile.billing_provider,
        'manage_url': apple_iap.APPLE_MANAGE_URL if apple_managed else None,
        'cancel_at_period_end': user_profile.subscription_cancel_at_period_end,
        # Pending deferred downgrade: -1/null means none. When set, the user keeps
        # `tier` until `period_end`, then switches to `change_at_period_end`.
        'change_at_period_end': pending_change if pending_change != -1 else None,
        'change_at_period_end_name': TIER_NAMES.get(pending_change) if pending_change != -1 else None,
        'period_end': period_end.isoformat() if period_end else None,
        'starred_members_limit': user_profile.get_starred_memberships_limit(),
        'starred_bills_limit': user_profile.get_starred_bills_limit(),
        'daily_prediction_credits': user_profile.get_daily_prediction_credits() if user_profile.get_daily_prediction_credits() < 10000 else None,
        'chat_messages_per_day': user_profile.get_chat_limit() if user_profile.get_chat_limit() < 10000 else None,
        # JSON key kept for mobile compatibility; value is now the cost-weighted
        # monthly budget (input + 5*output tokens).
        'chat_monthly_input_token_limit': user_profile.get_monthly_token_budget() or None,
    })


# Mobile REST endpoint: returns a Stripe Checkout URL for the app to open in a browser
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_create_checkout_session(request):
    if not getattr(settings, 'SUBSCRIPTIONS_ENABLED', True):
        return Response({'error': 'Subscriptions are temporarily unavailable.'}, status=503)

    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Checked before the tier is even parsed: an App Store subscriber must be
    # sent to Apple, not told their plan choice was invalid.
    apple_managed = _apple_managed_response(user_profile)
    if apple_managed:
        return apple_managed

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

    if user_profile.stripe_subscription_id:
        if tier == user_profile.user_type:
            # Re-selecting the current tier while a cancellation is pending resumes
            # the subscription (un-cancels it) so the user keeps their plan.
            if user_profile.subscription_cancel_at_period_end:
                try:
                    _reactivate_subscription(user_profile)
                except stripe.error.StripeError as exc:
                    logger.error('Stripe subscription resume failed (mobile): %s', exc)
                    return Response({'error': 'Could not resume your subscription.'}, status=502)
                return Response({
                    'modified': True,
                    'resumed': True,
                    'tier': user_profile.user_type,
                    'tier_name': TIER_NAMES.get(user_profile.user_type, 'Free'),
                    'cancel_at_period_end': False,
                    'change_at_period_end': -1,
                    'message': f'Your subscription was resumed. You will stay on {TIER_NAMES.get(user_profile.user_type, "Free")}.',
                }, status=200)
            # Re-selecting the current tier while a downgrade is pending cancels
            # that scheduled change so the user stays put.
            if user_profile.subscription_change_at_period_end != -1:
                _cancel_scheduled_change(user_profile)
                return Response({
                    'modified': True,
                    'change_cancelled': True,
                    'tier': user_profile.user_type,
                    'tier_name': TIER_NAMES.get(user_profile.user_type, 'Free'),
                    'change_at_period_end': -1,
                    'message': f'Your scheduled plan change was cancelled. You will stay on {TIER_NAMES.get(user_profile.user_type, "Free")}.',
                }, status=200)
            return Response({'error': 'You are already on this plan.'}, status=409)
        result = _modify_subscription_api(user_profile, tier, price_id)
        status_code = result.pop('status_code', 200)
        return Response(result, status=status_code)

    customer_id = _get_or_create_stripe_customer(user_profile, request.user)

    # Mobile sessions bounce back into the app via the deep-link return view (the
    # webhook is still the source of truth for the tier flip -- these URLs are UX
    # only and just get the in-app browser to close and the app to resume).
    base = request.build_absolute_uri(reverse('return_to_app'))
    success_url = f'{base}?status=success'
    cancel_url = f'{base}?status=cancel'

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


def _build_change_preview(user_profile, tier, price_id):
    """Compute a tier-change preview for an existing/about-to-be subscriber.

    Returns (data_dict, http_status). Shared by the web confirmation page
    (confirm_subscription_change) and the mobile preview endpoint
    (api_preview_subscription_change) so both quote identical numbers. The
    upgrade branch mirrors the params in _execute_tier_change exactly so the
    quoted charge matches what the customer is actually billed.
    """
    if tier == user_profile.user_type:
        return {'error': 'You are already on this plan.'}, 409

    # No existing subscription: confirming would open a fresh hosted Checkout,
    # not an in-place tier change, so there is nothing to prorate.
    if not user_profile.stripe_subscription_id:
        return {
            'requires_checkout': True,
            'is_upgrade': True,
            'new_tier': tier,
            'new_tier_name': TIER_NAMES[tier],
            'immediate_charge': None,
            'recurring_price': TIER_DISPLAY_PRICE.get(tier, ''),
            'message': f'Subscribe to {TIER_NAMES[tier]} through secure checkout.',
        }, 200

    is_upgrade = _is_upgrade(tier, user_profile.user_type)

    # Downgrade: nothing is charged now; it takes effect at the next billing date.
    if not is_upgrade:
        period_end = user_profile.subscription_period_end
        return {
            'is_upgrade': False,
            'current_tier': user_profile.user_type,
            'current_tier_name': TIER_NAMES.get(user_profile.user_type, 'Free'),
            'new_tier': tier,
            'new_tier_name': TIER_NAMES[tier],
            'immediate_charge': 0,
            'recurring_price': TIER_DISPLAY_PRICE.get(tier, ''),
            'currency': 'usd',
            'effective_date': period_end.isoformat() if period_end else None,
            'message': f'Your plan will switch to {TIER_NAMES[tier]} at your next billing date. No charge today.',
        }, 200

    # Upgrade: ask Stripe to preview the immediate prorated invoice.
    try:
        sub = stripe.Subscription.retrieve(user_profile.stripe_subscription_id)
        items_data = getattr(getattr(sub, 'items', None), 'data', [])
        if not items_data:
            raise ValueError('Subscription has no items')
        item_id = getattr(items_data[0], 'id', None)

        # Mirror _execute_tier_change exactly so the quote matches the real charge.
        # In particular, do NOT reset the billing cycle -- see the note there.
        preview = stripe.Invoice.create_preview(
            customer=user_profile.stripe_customer_id,
            subscription=user_profile.stripe_subscription_id,
            subscription_details={
                'items': [{'id': item_id, 'price': price_id}],
                'proration_behavior': 'always_invoice',
            },
        )
    except stripe.error.StripeError as exc:
        logger.error('Stripe upgrade preview failed: %s', exc)
        return {'error': 'Could not calculate the upgrade cost. Please try again.'}, 502
    except Exception as exc:
        logger.error('Upgrade preview error: %s', exc, exc_info=True)
        return {'error': 'Something went wrong.'}, 500

    amount_due = getattr(preview, 'amount_due', None)
    if amount_due is None:
        amount_due = getattr(preview, 'total', 0) or 0

    # Split the proration lines into the new-tier charge (positive) and the
    # unused-old-tier credit (negative). For an in-period upgrade the credit can
    # never exceed the gross charge -- the net is always a charge, never a refund
    # -- so clamp the displayed credit to the gross charge. This guards the
    # frontend against ever showing a "return" larger than the re-charge, even if
    # Stripe's preview surfaces stacked/leftover credit lines from prior changes.
    gross_charge_cents = 0
    credit_cents = 0
    for line in getattr(getattr(preview, 'lines', None), 'data', []) or []:
        parent = getattr(line, 'parent', None)
        item_details = getattr(parent, 'subscription_item_details', None) if parent else None
        is_proration = getattr(item_details, 'proration', False) if item_details else False
        if not is_proration:
            continue
        amount = getattr(line, 'amount', 0) or 0
        if amount > 0:
            gross_charge_cents += amount
        elif amount < 0:
            credit_cents += amount

    immediate_charge = round(amount_due / 100, 2)
    credit_applied = round(min(abs(credit_cents), gross_charge_cents) / 100, 2)
    currency = getattr(preview, 'currency', 'usd')

    return {
        'is_upgrade': True,
        'current_tier': user_profile.user_type,
        'current_tier_name': TIER_NAMES.get(user_profile.user_type, 'Free'),
        'new_tier': tier,
        'new_tier_name': TIER_NAMES[tier],
        'immediate_charge': immediate_charge,
        'credit_applied': credit_applied,
        'recurring_price': TIER_DISPLAY_PRICE.get(tier, ''),
        'currency': currency,
        'message': (
            f"You'll be charged ${immediate_charge:.2f} today to upgrade to "
            f"{TIER_NAMES[tier]} immediately (the prorated difference for the rest "
            f"of this period). Your billing date stays the same."
        ),
    }, 200


# Mobile REST endpoint: JWT authenticated, previews the cost of changing tiers
# so the app can show a confirmation dialog before committing the change.
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_preview_subscription_change(request):
    if not getattr(settings, 'SUBSCRIPTIONS_ENABLED', True):
        return Response({'error': 'Subscriptions are temporarily unavailable.'}, status=503)

    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    apple_managed = _apple_managed_response(user_profile)
    if apple_managed:
        return apple_managed

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
    data, status_code = _build_change_preview(user_profile, tier, price_id)
    return Response(data, status=status_code)


# Mobile REST endpoint: JWT authenticated, returns a Stripe Billing Portal URL
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_billing_portal(request):
    _stripe_client()
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    apple_managed = _apple_managed_response(user_profile)
    if apple_managed:
        return apple_managed

    if not user_profile.stripe_customer_id:
        return Response({'error': 'No billing account found. Upgrade to a paid plan first.'}, status=404)

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=user_profile.stripe_customer_id,
            # Bounce back into the app (no status -> "manage"). Must NOT be the plain
            # web /subscription/manage/ page: mobile users aren't logged in on web.
            return_url=request.build_absolute_uri(reverse('return_to_app')),
        )
    except stripe.error.StripeError as exc:
        logger.error('Stripe billing portal error (mobile): %s', exc)
        return Response({'error': 'Unable to open billing portal. Please try again.'}, status=502)

    return Response({'portal_url': portal_session.url})

