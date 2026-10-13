"""Stripe billing: webhook state machine and the mobile subscription API.

Webhooks are signed for real with the test STRIPE_WEBHOOK_SECRET, so
stripe.Webhook.construct_event's verification actually runs. Outbound Stripe
calls are patched per method.
"""

import datetime
import hashlib
import hmac
import json
import time
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

import pytest
import stripe
from django.test import override_settings
from django.utils import timezone

from app.models import STARRED_BILLS_LIMITS, STARRED_MEMBERSHIPS_LIMITS, UserProfile
from tests.factories import jwt_headers, make_user

pytestmark = pytest.mark.django_db

WEBHOOK_SECRET = 'whsec_stub'
PERIOD_END = 1_900_000_000
PRICE = {1: 'price_plus_test', 4: 'price_plus_pro_test', 2: 'price_premium_test'}


# --- helpers ---------------------------------------------------------------

def _sign(payload, secret=WEBHOOK_SECRET, ts=None):
    ts = ts or int(time.time())
    sig = hmac.new(secret.encode(), f'{ts}.{payload}'.encode(), hashlib.sha256).hexdigest()
    return f't={ts},v1={sig}'


def _send(client, event_type, obj, secret=WEBHOOK_SECRET):
    payload = json.dumps({'id': 'evt_1', 'object': 'event', 'type': event_type,
                          'data': {'object': obj}})
    return client.post('/api/stripe/webhook/', payload, content_type='application/json',
                       HTTP_STRIPE_SIGNATURE=_sign(payload, secret))


def _sub_obj(customer='cus_1', price=PRICE[2], status='active', cancel_at=None, **extra):
    return {
        'id': 'sub_1', 'object': 'subscription', 'customer': customer, 'status': status,
        'cancel_at': cancel_at, 'cancel_at_period_end': False, 'schedule': None,
        'items': {'object': 'list', 'data': [
            {'id': 'si_1', 'current_period_end': PERIOD_END, 'price': {'id': price}},
        ]},
        **extra,
    }


def _stripe_sub(**kw):
    return stripe.Subscription.construct_from(_sub_obj(**kw), 'sk_test')


def _profile(user):
    return UserProfile.objects.get(user=user)


def _subscriber(tier=1, **kw):
    user = make_user(tier=tier, stripe_customer_id='cus_1', stripe_subscription_id='sub_1',
                     billing_provider='stripe', **kw)
    return user


@contextmanager
def stripe_calls(**overrides):
    """Patch every outbound Stripe call; anything not overridden returns a MagicMock."""
    targets = {
        'retrieve': (stripe.Subscription, 'retrieve'),
        'modify': (stripe.Subscription, 'modify'),
        'release': (stripe.SubscriptionSchedule, 'release'),
        'customer_create': (stripe.Customer, 'create'),
        'checkout_create': (stripe.checkout.Session, 'create'),
        'portal_create': (stripe.billing_portal.Session, 'create'),
    }
    patches = {name: mock.patch.object(obj, attr, **overrides.get(name, {}))
               for name, (obj, attr) in targets.items()}
    mocks = {name: p.start() for name, p in patches.items()}
    try:
        yield SimpleNamespace(**mocks)
    finally:
        for p in patches.values():
            p.stop()


# --- webhook ---------------------------------------------------------------

class TestWebhookSecurity:
    def test_bad_signature(self, client):
        assert _send(client, 'customer.subscription.deleted', _sub_obj(), secret='whsec_wrong').status_code == 400

    def test_missing_signature(self, client):
        assert client.post('/api/stripe/webhook/', '{}', content_type='application/json').status_code == 400

    def test_stale_timestamp(self, client):
        payload = json.dumps({'id': 'evt', 'type': 'x', 'data': {'object': {}}})
        resp = client.post('/api/stripe/webhook/', payload, content_type='application/json',
                           HTTP_STRIPE_SIGNATURE=_sign(payload, ts=int(time.time()) - 3600))
        assert resp.status_code == 400

    def test_get_not_allowed(self, client):
        assert client.get('/api/stripe/webhook/').status_code == 405

    def test_unhandled_event_type_ok(self, client):
        assert _send(client, 'invoice.paid', {'id': 'in_1'}).status_code == 200


class TestCheckoutCompleted:
    def _session(self, user, tier='1'):
        return {'id': 'cs_1', 'object': 'checkout.session', 'subscription': 'sub_9',
                'metadata': {'user_id': str(user.id), 'tier': tier}}

    def test_grants_tier(self, client, free_user):
        with stripe_calls(retrieve={'return_value': _stripe_sub()}) as s:
            assert _send(client, 'checkout.session.completed', self._session(free_user)).status_code == 200
        s.retrieve.assert_called_once_with('sub_9')
        p = _profile(free_user)
        assert (p.user_type, p.stripe_subscription_id, p.billing_provider) == (1, 'sub_9', 'stripe')
        assert p.subscription_period_end == datetime.datetime.fromtimestamp(PERIOD_END, datetime.timezone.utc)
        assert (p.subscription_cancel_at_period_end, p.subscription_change_at_period_end) == (False, -1)

    def test_tier_still_granted_if_retrieve_fails(self, client, free_user):
        with stripe_calls(retrieve={'side_effect': stripe.error.APIConnectionError('down')}):
            _send(client, 'checkout.session.completed', self._session(free_user, tier='2'))
        assert _profile(free_user).user_type == 2

    def test_missing_metadata_ignored(self, client, free_user):
        obj = {'id': 'cs_1', 'object': 'checkout.session', 'subscription': 'sub_9', 'metadata': {}}
        with stripe_calls():
            assert _send(client, 'checkout.session.completed', obj).status_code == 200
        assert _profile(free_user).user_type == 0

    def test_unknown_user_ignored(self, client):
        obj = {'id': 'cs_1', 'object': 'checkout.session', 'subscription': 'sub_9',
               'metadata': {'user_id': '999999', 'tier': '1'}}
        with stripe_calls():
            assert _send(client, 'checkout.session.completed', obj).status_code == 200


class TestSubscriptionUpdated:
    def test_price_change_sets_tier(self, client):
        user = _subscriber(tier=1)
        assert _send(client, 'customer.subscription.updated', _sub_obj(price=PRICE[2])).status_code == 200
        p = _profile(user)
        assert p.user_type == 2
        assert p.subscription_period_end is not None

    def test_created_event_handled_the_same(self, client):
        user = _subscriber(tier=0)
        _send(client, 'customer.subscription.created', _sub_obj(price=PRICE[4]))
        assert _profile(user).user_type == 4

    @pytest.mark.parametrize('status', ['past_due', 'incomplete', 'unpaid'])
    def test_unpaid_upgrade_not_granted(self, client, status):
        user = _subscriber(tier=1)
        _send(client, 'customer.subscription.updated', _sub_obj(price=PRICE[2], status=status))
        assert _profile(user).user_type == 1

    def test_unknown_price_keeps_tier(self, client):
        user = _subscriber(tier=1)
        _send(client, 'customer.subscription.updated', _sub_obj(price='price_unknown'))
        assert _profile(user).user_type == 1

    def test_pending_cancellation_supersedes_downgrade(self, client):
        user = _subscriber(tier=2, subscription_change_at_period_end=1)
        _send(client, 'customer.subscription.updated', _sub_obj(price=PRICE[2], cancel_at=PERIOD_END))
        p = _profile(user)
        assert p.subscription_cancel_at_period_end is True
        assert p.subscription_change_at_period_end == 0

    def test_resumed_clears_free_marker(self, client):
        user = _subscriber(tier=2, subscription_cancel_at_period_end=True, subscription_change_at_period_end=0)
        _send(client, 'customer.subscription.updated', _sub_obj(price=PRICE[2]))
        p = _profile(user)
        assert (p.subscription_cancel_at_period_end, p.subscription_change_at_period_end) == (False, -1)

    def test_deferred_downgrade_takes_effect(self, client):
        user = _subscriber(tier=2, subscription_change_at_period_end=1)
        _send(client, 'customer.subscription.updated', _sub_obj(price=PRICE[1]))
        p = _profile(user)
        assert (p.user_type, p.subscription_change_at_period_end) == (1, -1)

    def test_unknown_customer(self, client):
        assert _send(client, 'customer.subscription.updated', _sub_obj(customer='cus_ghost')).status_code == 200


class TestSubscriptionDeleted:
    def test_drops_to_free(self, client):
        user = _subscriber(tier=2, subscription_cancel_at_period_end=True, subscription_change_at_period_end=0)
        assert _send(client, 'customer.subscription.deleted', _sub_obj()).status_code == 200
        p = _profile(user)
        assert (p.user_type, p.stripe_subscription_id, p.subscription_period_end) == (0, None, None)
        assert (p.subscription_cancel_at_period_end, p.subscription_change_at_period_end) == (False, -1)
        assert p.stripe_customer_id == 'cus_1'


def test_handler_errors_still_return_200(client):
    with mock.patch('app.subscription_views._handle_subscription_deleted', side_effect=RuntimeError('boom')):
        assert _send(client, 'customer.subscription.deleted', _sub_obj()).status_code == 200


# --- mobile API ------------------------------------------------------------

@pytest.fixture
def authed(api_client):
    def _authed(user):
        api_client.credentials(**jwt_headers(user))
        return api_client
    return _authed


class TestPlans:
    def test_public(self, api_client):
        resp = api_client.get('/api/subscription/plans/')
        assert resp.status_code == 200
        assert [t['id'] for t in resp.data['tiers']] == [0, 1, 4, 2]
        assert resp.data['subscriptions_enabled'] is True

    @pytest.mark.parametrize('tier', [0, 1, 4, 2])
    def test_every_advertised_limit_matches_model(self, api_client, tier):
        # The plans screen is hand-written; this keeps it honest against what
        # the code enforces (and tier_limits.md, checked against the same tables).
        from app import models as m
        advertised = {t['id']: t for t in api_client.get('/api/subscription/plans/').data['tiers']}[tier]
        unlimited = lambda n: None if n >= 10_000 else n
        assert advertised['starred_bills_limit'] == m.STARRED_BILLS_LIMITS[tier]
        assert advertised['starred_members_limit'] == m.STARRED_MEMBERSHIPS_LIMITS[tier]
        assert advertised['predictions_per_day'] == unlimited(m.DAILY_PREDICTION_CREDITS[tier])
        assert advertised['chat_messages_per_day'] == unlimited(m.DAILY_CHAT_LIMITS[tier])
        assert advertised['chat_monthly_input_token_limit'] == (m.MONTHLY_TOKEN_BUDGETS[tier] or None)
        assert advertised['chat_monthly_web_search_limit'] == m.MONTHLY_WEB_SEARCH_LIMITS[tier]


class TestStatus:
    def test_anonymous(self, api_client):
        assert api_client.get('/api/subscription/status/').status_code == 401

    def test_free(self, authed, free_user):
        data = authed(free_user).get('/api/subscription/status/').data
        assert (data['tier'], data['tier_name'], data['billing_provider']) == (0, 'Free', None)
        assert data['change_at_period_end'] is None
        assert data['chat_monthly_input_token_limit'] is None

    def test_premium_unlimited_fields_are_null(self, authed, premium_user):
        data = authed(premium_user).get('/api/subscription/status/').data
        assert data['chat_messages_per_day'] is None
        assert data['daily_prediction_credits'] is None
        assert data['chat_monthly_input_token_limit'] == 5_000_000

    def test_pending_downgrade(self, authed):
        user = _subscriber(tier=2, subscription_change_at_period_end=1)
        data = authed(user).get('/api/subscription/status/').data
        assert (data['change_at_period_end'], data['change_at_period_end_name']) == (1, 'Plus')


class TestCreateCheckout:
    URL = '/api/subscription/create-checkout/'

    def test_new_subscriber(self, authed, free_user):
        with stripe_calls(customer_create={'return_value': SimpleNamespace(id='cus_new')},
                          checkout_create={'return_value': SimpleNamespace(url='https://checkout.stripe.test/x')}) as s:
            resp = authed(free_user).post(self.URL, {'tier': 1}, format='json')
        assert resp.status_code == 200
        assert resp.data == {'checkout_url': 'https://checkout.stripe.test/x'}
        kwargs = s.checkout_create.call_args.kwargs
        assert kwargs['customer'] == 'cus_new'
        assert kwargs['line_items'] == [{'price': PRICE[1], 'quantity': 1}]
        assert kwargs['metadata'] == {'user_id': str(free_user.id), 'tier': '1'}
        assert kwargs['success_url'].endswith('/subscription/return-to-app/?status=success')
        assert _profile(free_user).stripe_customer_id == 'cus_new'

    def test_existing_customer_reused(self, authed):
        user = make_user(stripe_customer_id='cus_old')
        with stripe_calls(checkout_create={'return_value': SimpleNamespace(url='u')}) as s:
            authed(user).post(self.URL, {'tier': 2}, format='json')
        s.customer_create.assert_not_called()

    @pytest.mark.parametrize('tier', ['x', '', 0, 3, 99])
    def test_invalid_tier(self, authed, free_user, tier):
        with stripe_calls():
            assert authed(free_user).post(self.URL, {'tier': tier}, format='json').status_code == 400

    def test_already_on_plan(self, authed):
        with stripe_calls():
            assert authed(_subscriber(tier=1)).post(self.URL, {'tier': 1}, format='json').status_code == 409

    def test_stripe_error(self, authed, free_user):
        with stripe_calls(customer_create={'return_value': SimpleNamespace(id='cus_new')},
                          checkout_create={'side_effect': stripe.error.APIConnectionError('down')}):
            assert authed(free_user).post(self.URL, {'tier': 1}, format='json').status_code == 502

    @override_settings(SUBSCRIPTIONS_ENABLED=False)
    def test_disabled(self, authed, free_user):
        assert authed(free_user).post(self.URL, {'tier': 1}, format='json').status_code == 503


class TestCancelAndReactivate:
    def test_cancel(self, authed):
        user = _subscriber(tier=2, subscription_change_at_period_end=1)
        with stripe_calls(retrieve={'return_value': _stripe_sub()}) as s:
            resp = authed(user).post('/api/subscription/cancel/')
        assert resp.status_code == 200
        s.modify.assert_called_once_with('sub_1', cancel_at='min_period_end')
        s.release.assert_not_called()
        p = _profile(user)
        assert (p.subscription_cancel_at_period_end, p.subscription_change_at_period_end) == (True, 0)
        assert resp.data['change_at_period_end_name'] == 'Free'

    def test_cancel_releases_schedule(self, authed):
        user = _subscriber(tier=2)
        with stripe_calls(retrieve={'return_value': _stripe_sub(schedule='sub_sched_1')}) as s:
            authed(user).post('/api/subscription/cancel/')
        s.release.assert_called_once_with('sub_sched_1')

    def test_cancel_without_subscription(self, authed, free_user):
        assert authed(free_user).post('/api/subscription/cancel/').status_code == 404

    def test_cancel_twice(self, authed):
        user = _subscriber(tier=2, subscription_cancel_at_period_end=True)
        assert authed(user).post('/api/subscription/cancel/').status_code == 409

    def test_cancel_stripe_error_leaves_profile(self, authed):
        user = _subscriber(tier=2)
        with stripe_calls(retrieve={'side_effect': stripe.error.APIConnectionError('down')}):
            assert authed(user).post('/api/subscription/cancel/').status_code == 502
        assert _profile(user).subscription_cancel_at_period_end is False

    def test_reactivate(self, authed):
        user = _subscriber(tier=2, subscription_cancel_at_period_end=True, subscription_change_at_period_end=0)
        with stripe_calls() as s:
            resp = authed(user).post('/api/subscription/reactivate/')
        assert resp.status_code == 200
        s.modify.assert_called_once_with('sub_1', cancel_at='')
        p = _profile(user)
        assert (p.subscription_cancel_at_period_end, p.subscription_change_at_period_end) == (False, -1)

    def test_reactivate_when_not_cancelling(self, authed):
        assert authed(_subscriber(tier=2)).post('/api/subscription/reactivate/').status_code == 409


class TestBillingPortal:
    def test_portal(self, authed):
        with stripe_calls(portal_create={'return_value': SimpleNamespace(url='https://billing.stripe.test')}) as s:
            resp = authed(_subscriber()).post('/api/subscription/portal/')
        assert resp.data == {'portal_url': 'https://billing.stripe.test'}
        assert s.portal_create.call_args.kwargs['return_url'].endswith('/subscription/return-to-app/')

    def test_no_customer(self, authed, free_user):
        assert authed(free_user).post('/api/subscription/portal/').status_code == 404


class TestAppleManagedGuard:
    """An App Store subscription can't be changed through Stripe."""

    @pytest.fixture
    def apple_user(self):
        return make_user(tier=2, billing_provider='apple', apple_original_transaction_id='2000000000000001',
                         subscription_period_end=timezone.now() + datetime.timedelta(days=10),
                         stripe_customer_id='cus_1', stripe_subscription_id='sub_1')

    @pytest.mark.parametrize('url, data', [
        ('/api/subscription/create-checkout/', {'tier': 1}),
        ('/api/subscription/preview-change/', {'tier': 1}),
        ('/api/subscription/cancel/', {}),
        ('/api/subscription/reactivate/', {}),
        ('/api/subscription/portal/', {}),
    ])
    def test_stripe_mutations_refused(self, authed, apple_user, url, data):
        with stripe_calls() as s:
            resp = authed(apple_user).post(url, data, format='json')
        assert resp.status_code == 409
        assert resp.data['billing_provider'] == 'apple'
        s.modify.assert_not_called()
        s.checkout_create.assert_not_called()

    def test_status_shows_manage_url(self, authed, apple_user):
        assert authed(apple_user).get('/api/subscription/status/').data['manage_url']

    def test_expired_apple_sub_not_guarded(self, authed, apple_user):
        UserProfile.objects.filter(user=apple_user).update(
            subscription_period_end=timezone.now() - datetime.timedelta(days=1))
        with stripe_calls(portal_create={'return_value': SimpleNamespace(url='u')}):
            assert authed(apple_user).post('/api/subscription/portal/').status_code == 200


@pytest.mark.parametrize('status, expected', [
    ('success', 'success'), ('cancel', 'cancel'), ('manage', 'manage'),
    (None, 'manage'), ('javascript:alert(1)', 'manage'),
])
def test_return_to_app(client, status, expected):
    resp = client.get('/subscription/return-to-app/', {'status': status} if status else {})
    assert resp.status_code == 302
    assert resp['Location'] == f'usqmobileapp://subscription/manage?status={expected}'
