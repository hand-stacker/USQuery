"""Scheduled management commands, run with call_command under test settings."""

import datetime
from io import StringIO
from unittest import mock

import pytest
import stripe
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.utils import timezone
from freezegun import freeze_time

from app import apple_iap
from app.management.commands import send_floor_notifications as floor_cmd
from app.models import AppleSubscription, EmailVerification, UserProfile
from BillQuery.models import Bill
from notifications.models import StarredBill, StarredMembership
from tests.factories import make_bill, make_user

pytestmark = pytest.mark.django_db


def run(*args, **kwargs):
    out = StringIO()
    call_command(*args, stdout=out, stderr=out, **kwargs)
    return out.getvalue()


class TestTrimStarredItems:
    def test_downgrade_trims_oldest(self):
        user = make_user(tier=2)
        profile = user.userprofile
        bills = StarredBill.objects.bulk_create(
            [StarredBill(user_profile=profile, bill_id=str(i)) for i in range(12)])
        for i, b in enumerate(bills):
            StarredBill.objects.filter(pk=b.pk).update(created_at=timezone.now() - datetime.timedelta(days=100 - i))
        StarredMembership.objects.bulk_create(
            [StarredMembership(user_profile=profile, membership_id=i) for i in range(4)])
        UserProfile.objects.filter(pk=profile.pk).update(user_type=0)  # Free: 10 bills, 3 members

        out = run('trim_starred_items')

        assert 'Trimmed 2 bill(s) and 1 membership(s)' in out
        inactive = set(StarredBill.objects.filter(is_active=False).values_list('bill_id', flat=True))
        assert inactive == {'0', '1'}
        assert StarredMembership.objects.filter(is_active=True).count() == 3

    def test_within_limits_untouched(self, plus_user):
        StarredBill.objects.create(user_profile=plus_user.userprofile, bill_id='1')
        assert 'Trimmed 0 bill(s) and 0 membership(s)' in run('trim_starred_items')


class TestCleanupVerifications:
    def test_deletes_only_expired_unverified(self):
        stale = make_user(active=False)
        fresh = make_user(active=False)
        verified = make_user(active=True)
        with freeze_time(timezone.now() - datetime.timedelta(minutes=30)):
            EmailVerification.objects.create(user=stale)
            EmailVerification.objects.create(user=verified)
        EmailVerification.objects.create(user=fresh)
        assert 'Deleted 1 expired' in run('cleanup_verifications')
        assert set(EmailVerification.objects.values_list('user_id', flat=True)) == {fresh.id, verified.id}


class TestDeleteScheduledUsers:
    def test_deletes_and_cancels_stripe(self):
        doomed = make_user(scheduled_for_deletion=True, stripe_subscription_id='sub_1')
        StarredBill.objects.create(user_profile=doomed.userprofile, bill_id='1')
        keeper = make_user()
        with mock.patch.object(stripe.Subscription, 'cancel') as cancel:
            out = run('delete_scheduled_users')
        cancel.assert_called_once_with('sub_1')
        assert 'Deleted 1 user(s)' in out
        assert list(User.objects.values_list('id', flat=True)) == [keeper.id]
        assert not StarredBill.objects.exists()

    def test_stripe_failure_does_not_block_deletion(self):
        make_user(scheduled_for_deletion=True, stripe_subscription_id='sub_1')
        with mock.patch.object(stripe.Subscription, 'cancel', side_effect=stripe.error.APIConnectionError('down')):
            run('delete_scheduled_users')
        assert not User.objects.exists()

    def test_apple_subscriber_logged(self, caplog):
        caplog.set_level('WARNING', logger='app.management.commands.delete_scheduled_users')
        make_user(scheduled_for_deletion=True, apple_original_transaction_id='2000000000000001')
        with mock.patch.object(stripe.Subscription, 'cancel') as cancel:
            run('delete_scheduled_users')
        cancel.assert_not_called()
        assert any('App Store subscription' in r.getMessage() for r in caplog.records)


class TestSetAppVersion:
    def test_sets_cache(self):
        run('set_app_version', ' 2.4.0 ')
        assert cache.get('app_version') == '2.4.0'

    def test_empty_rejected(self):
        with pytest.raises(CommandError):
            run('set_app_version', '  ')




class TestSendFloorNotifications:
    @pytest.fixture
    def send(self):
        with mock.patch.object(floor_cmd, 'send_floor_notification', mock.AsyncMock()) as m:
            yield m

    @freeze_time('2026-03-02 14:00:00')
    def test_matches_users_by_local_hour(self, send):
        on_time = make_user(enabled_house_floor_notif=True, house_floor_notif_time=9, house_floor_notif_timezone='EST')
        make_user(enabled_house_floor_notif=True, house_floor_notif_time=10, house_floor_notif_timezone='EST')
        make_user(enabled_house_floor_notif=True, house_floor_notif_time=9, house_floor_notif_timezone='EST',
                  house_floor_notif_frequency=0)
        cache.set('floor_notif_house', {'date': '2026-03-02', 'bill_ids': [11940001]})
        run('send_floor_notifications')
        send.assert_awaited_once_with('house', [11940001], [on_time.userprofile.id])

    @freeze_time('2026-03-02 14:00:00')
    def test_stale_cache_ignored(self, send):
        make_user(enabled_house_floor_notif=True, house_floor_notif_time=9, house_floor_notif_timezone='EST')
        cache.set('floor_notif_house', {'date': '2026-03-01', 'bill_ids': [11940001]})
        run('send_floor_notifications')
        send.assert_not_awaited()


class TestSyncAppleSubscriptions:
    @pytest.fixture
    def subs(self):
        user = make_user(tier=1)
        soon = AppleSubscription.objects.create(
            original_transaction_id='1', user=user, product_id='p', tier=1, environment='Production',
            expires_date=timezone.now() + datetime.timedelta(hours=1))
        AppleSubscription.objects.create(
            original_transaction_id='2', user=make_user(), product_id='p', tier=1, environment='Production',
            expires_date=timezone.now() + datetime.timedelta(days=20))
        return soon

    def test_window_and_apply(self, subs):
        with mock.patch.object(apple_iap, 'fetch_subscription_state', return_value={'tier': 2}) as fetch, \
             mock.patch.object(apple_iap, 'apply_state', return_value=True) as apply:
            out = run('sync_apple_subscriptions')
        assert fetch.call_count == 1
        apply.assert_called_once_with(subs.user, {'tier': 2})
        assert 'Updated 1, skipped 0' in out

    def test_all_and_dry_run(self, subs):
        with mock.patch.object(apple_iap, 'fetch_subscription_state', return_value={'tier': 2}) as fetch, \
             mock.patch.object(apple_iap, 'apply_state') as apply:
            run('sync_apple_subscriptions', '--all', '--dry-run')
        assert fetch.call_count == 2
        apply.assert_not_called()

    def test_fetch_failure_counted(self, subs):
        with mock.patch.object(apple_iap, 'fetch_subscription_state', return_value=None):
            assert 'failed 1' in run('sync_apple_subscriptions')
