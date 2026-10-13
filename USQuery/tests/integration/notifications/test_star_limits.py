"""Tier enforcement in Device / StarredBill / StarredMembership .clean()."""

import pytest
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.utils import timezone

from notifications.models import Device, FavoriteSubject, StarredBill, StarredMembership

pytestmark = pytest.mark.django_db


def _codes(exc_info):
    return [e.code for e in exc_info.value.error_dict.get(NON_FIELD_ERRORS, [])]


@pytest.fixture
def profile(free_user):
    return free_user.userprofile


class TestStarredBills:
    LIMIT = 10  # Free

    def _fill(self, profile, n=LIMIT):
        return [StarredBill.objects.create(user_profile=profile, bill_id=str(i)) for i in range(n)]

    def test_at_limit_rejected(self, profile):
        self._fill(profile)
        with pytest.raises(ValidationError) as exc:
            StarredBill.objects.create(user_profile=profile, bill_id='overflow')
        assert _codes(exc) == ['BillLimit']
        assert StarredBill.objects.filter(user_profile=profile).count() == self.LIMIT

    def test_inactive_rows_dont_count(self, profile):
        rows = self._fill(profile)
        StarredBill.objects.filter(pk=rows[0].pk).update(is_active=False)
        StarredBill.objects.create(user_profile=profile, bill_id='new')

    def test_resaving_existing_row_at_limit(self, profile):
        rows = self._fill(profile)
        rows[0].save()

    def test_upgrade_raises_limit(self, profile):
        self._fill(profile)
        profile.user_type = 1  # Plus: 50
        profile.save()
        StarredBill.objects.create(user_profile=profile, bill_id='new')

    def test_null_profile_skips_check(self):
        StarredBill.objects.create(user_profile=None, bill_id='orphan')

    def test_duplicate_rejected(self, profile):
        StarredBill.objects.create(user_profile=profile, bill_id='1')
        with pytest.raises(ValidationError):
            StarredBill.objects.create(user_profile=profile, bill_id='1')


class TestStarredMemberships:
    def test_free_limit_is_three(self, profile):
        for i in range(3):
            StarredMembership.objects.create(user_profile=profile, membership_id=i)
        with pytest.raises(ValidationError) as exc:
            StarredMembership.objects.create(user_profile=profile, membership_id=99)
        assert _codes(exc) == ['MembershipLimit']

    def test_inactive_rows_dont_count(self, profile):
        rows = [StarredMembership.objects.create(user_profile=profile, membership_id=i) for i in range(3)]
        StarredMembership.objects.filter(pk=rows[0].pk).update(is_active=False)
        StarredMembership.objects.create(user_profile=profile, membership_id=99)


class TestDevices:
    def test_limit(self, profile):
        for i in range(5):
            Device.objects.create(user_profile=profile, device_token=f'tok{i}', platform='ios')
        with pytest.raises(ValidationError) as exc:
            Device.objects.create(user_profile=profile, device_token='tok-extra', platform='ios')
        assert _codes(exc) == ['DeviceLimit']

    def test_deactivate_frees_slot(self, profile):
        devices = [Device.objects.create(user_profile=profile, device_token=f'tok{i}', platform='ios')
                   for i in range(5)]
        devices[0].deactivate()
        Device.objects.create(user_profile=profile, device_token='tok-extra', platform='android')

    def test_token_unique(self, profile):
        Device.objects.create(user_profile=profile, device_token='same', platform='ios')
        with pytest.raises(ValidationError):
            Device.objects.create(user_profile=profile, device_token='same', platform='ios')

    def test_refresh_last_used_is_aware(self, profile):
        device = Device.objects.create(user_profile=profile, device_token='t', platform='ios')
        device.refresh_last_used()
        assert timezone.is_aware(device.last_used)


def test_favorite_subjects_have_no_limit(profile):
    # Asymmetry worth knowing: FavoriteSubject has no clean()/tier check.
    for i in range(50):
        FavoriteSubject.objects.create(user_profile=profile, subject_id=i)
    assert profile.get_favorite_subjects().count() == 50
