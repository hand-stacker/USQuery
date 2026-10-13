"""Expo push fan-out (notifications/push.py). requests.post is patched."""

from unittest import mock

import pytest

from notifications import push
from notifications.models import Device, FavoriteSubject, StarredBill
from tests.factories import make_user

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def post():
    with mock.patch.object(push.requests, 'post') as m:
        yield m


def _device(user, token, active=True):
    return Device.objects.create(user_profile=user.userprofile, device_token=token, platform='ios', is_active=active)


def _sent_tokens(post):
    return [m['to'] for call in post.call_args_list for m in call.kwargs['json']]


class TestBillNotification:
    async def test_starred_users_active_devices(self, post):
        fan = await make_user_async()
        await _star(fan, '11940001')
        await _device_async(fan, 'tok-a')
        await _device_async(fan, 'tok-off', active=False)
        other = await make_user_async()
        await _device_async(other, 'tok-other')
        await push.send_bill_notification(11940001, 'T', 'B')
        assert _sent_tokens(post) == ['tok-a']
        msg = post.call_args.kwargs['json'][0]
        assert msg['data'] == {'screen': 'Bill_info', 'bill_id': 11940001}
        assert post.call_args.args[0] == push.EXPO_PUSH_URL

    async def test_respects_bill_notif_preference(self, post):
        fan = await make_user_async(enabled_bill_notif=False)
        await _star(fan, '1')
        await _device_async(fan, 'tok')
        await push.send_bill_notification(1, 'T', 'B')
        post.assert_not_called()

    async def test_nobody_starred(self, post):
        await push.send_bill_notification(1, 'T', 'B')
        post.assert_not_called()

    async def test_unstarred_users_not_notified(self, post):
        fan = await make_user_async()
        await _star(fan, '1', active=False)
        await _device_async(fan, 'tok')
        await push.send_bill_notification(1, 'T', 'B')
        post.assert_not_called()

    async def test_batches_of_100(self, post):
        special = await make_user_async(tier=3)
        await _star(special, '1')
        await Device.objects.abulk_create([
            Device(user_profile=special.userprofile, device_token=f't{i}', platform='ios') for i in range(250)])
        await push.send_bill_notification(1, 'T', 'B')
        assert [len(c.kwargs['json']) for c in post.call_args_list] == [100, 100, 50]


class TestSubjectNotification:
    async def test_favorite_subject_fans(self, post):
        fan = await make_user_async()
        await FavoriteSubject.objects.acreate(user_profile=fan.userprofile, subject_id=7)
        await _device_async(fan, 'tok')
        await push.send_subject_notification({7, 8}, 'T', 'B')
        assert _sent_tokens(post) == ['tok']

    async def test_removed_favorites_not_notified(self, post):
        fan = await make_user_async()
        await FavoriteSubject.objects.acreate(user_profile=fan.userprofile, subject_id=7, is_active=False)
        await _device_async(fan, 'tok')
        await push.send_subject_notification({7}, 'T', 'B')
        post.assert_not_called()


class TestFloorNotification:
    async def test_payload(self, post):
        user = await make_user_async()
        await _device_async(user, 'tok')
        await push.send_floor_notification('senate', [1, 2], [user.userprofile.id])
        msg = post.call_args.kwargs['json'][0]
        assert msg['title'] == 'Senate Floor Activity'
        assert msg['data']['filters'] == {'type': 'Senate'} and msg['data']['highlight'] == [1, 2]

    @pytest.mark.parametrize('bill_ids, profile_ids', [([], [1]), ([1], [])])
    async def test_noop_without_targets(self, post, bill_ids, profile_ids):
        await push.send_floor_notification('house', bill_ids, profile_ids)
        post.assert_not_called()


# --- async helpers -----------------------------------------------------------

from asgiref.sync import sync_to_async  # noqa: E402

make_user_async = sync_to_async(make_user)
_device_async = sync_to_async(_device)


@sync_to_async
def _star(user, bill_id, active=True):
    return StarredBill.objects.create(user_profile=user.userprofile, bill_id=bill_id, is_active=active)
