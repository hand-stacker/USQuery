import datetime
from types import SimpleNamespace

import pytest
import stripe
from django.test import override_settings

from app import subscription_views as sv

FREE, PLUS, PREMIUM, SPECIAL, PLUS_PRO = 0, 1, 2, 3, 4


class TestIsUpgrade:
    """Tier ids don't sort by plan level: Plus Pro (4) sits between Plus (1)
    and Premium (2). A raw id comparison would get these wrong."""

    @pytest.mark.parametrize('new, current', [
        (PLUS, FREE), (PLUS_PRO, PLUS), (PREMIUM, PLUS_PRO), (PREMIUM, PLUS), (SPECIAL, PREMIUM),
    ])
    def test_upgrades(self, new, current):
        assert sv._is_upgrade(new, current) is True

    @pytest.mark.parametrize('new, current', [
        (PLUS_PRO, PREMIUM), (PLUS, PLUS_PRO), (FREE, PLUS), (PLUS, PLUS),
    ])
    def test_not_upgrades(self, new, current):
        assert sv._is_upgrade(new, current) is False

    def test_unknown_tier_ranks_as_free(self):
        assert sv._is_upgrade(PLUS, 99) is True
        assert sv._is_upgrade(99, PLUS) is False


def test_price_to_tier_uses_configured_price_ids():
    assert sv._price_to_tier() == {
        'price_plus_test': PLUS,
        'price_plus_pro_test': PLUS_PRO,
        'price_premium_test': PREMIUM,
    }


@override_settings(STRIPE_PLUS_PRICE_ID='price_a', STRIPE_PLUS_PRO_PRICE_ID='price_b',
                   STRIPE_PREMIUM_PRICE_ID='price_c')
def test_price_to_tier_reads_settings_at_call_time():
    assert sv._price_to_tier() == {'price_a': PLUS, 'price_b': PLUS_PRO, 'price_c': PREMIUM}


class TestTimestamps:
    def test_none_and_zero(self):
        assert sv._ts_to_dt(None) is None
        assert sv._ts_to_dt(0) is None

    def test_aware_utc(self):
        dt = sv._ts_to_dt(1_700_000_000)
        assert dt == datetime.datetime(2023, 11, 14, 22, 13, 20, tzinfo=datetime.timezone.utc)


class TestPendingCancellation:
    def _sub(self, **fields):
        return stripe.Subscription.construct_from({'id': 'sub_1', **fields}, 'sk_test')

    def test_flexible_mode_cancel_at(self):
        assert sv._is_pending_cancellation(self._sub(cancel_at=1_700_000_000, cancel_at_period_end=False))

    def test_classic_mode_flag(self):
        assert sv._is_pending_cancellation(self._sub(cancel_at=None, cancel_at_period_end=True))

    def test_active(self):
        assert not sv._is_pending_cancellation(self._sub(cancel_at=None, cancel_at_period_end=False))

    def test_missing_fields(self):
        assert not sv._is_pending_cancellation(SimpleNamespace())


class TestSubscriptionPeriodEnd:
    def test_reads_first_item(self):
        sub = stripe.Subscription.construct_from({
            'id': 'sub_1',
            'items': {'object': 'list', 'data': [
                {'id': 'si_1', 'current_period_end': 1_700_000_000},
                {'id': 'si_2', 'current_period_end': 1_800_000_000},
            ]},
        }, 'sk_test')
        assert sv._subscription_period_end(sub) == sv._ts_to_dt(1_700_000_000)

    def test_no_items(self):
        assert sv._subscription_period_end(SimpleNamespace()) is None
        empty = stripe.Subscription.construct_from(
            {'id': 'sub_1', 'items': {'object': 'list', 'data': []}}, 'sk_test')
        assert sv._subscription_period_end(empty) is None


class TestPhaseItemPrice:
    def test_dict_with_id(self):
        assert sv._phase_item_price({'price': 'price_x'}) == 'price_x'

    def test_dict_with_expanded_price(self):
        assert sv._phase_item_price({'price': SimpleNamespace(id='price_y')}) == 'price_y'

    def test_object(self):
        assert sv._phase_item_price(SimpleNamespace(price='price_z')) == 'price_z'

    def test_missing_price(self):
        assert sv._phase_item_price(SimpleNamespace()) is None


def test_tier_names_cover_every_tier():
    assert set(sv.TIER_NAMES) == set(sv.TIER_RANKS) == {0, 1, 2, 3, 4}
