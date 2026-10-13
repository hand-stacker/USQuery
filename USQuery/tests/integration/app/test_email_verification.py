import datetime

import pytest
from freezegun import freeze_time

from app.models import EmailVerification

pytestmark = pytest.mark.django_db

START = datetime.datetime(2026, 3, 1, 23, 50, tzinfo=datetime.timezone.utc)


@pytest.fixture
def verification(free_user):
    with freeze_time(START):
        return EmailVerification.objects.create(user=free_user)


class TestIsValid:
    def test_ten_minute_window(self, verification):
        with freeze_time(START + datetime.timedelta(minutes=10)):
            assert verification.is_valid()
        with freeze_time(START + datetime.timedelta(minutes=10, seconds=1)):
            assert not verification.is_valid()


class TestResend:
    def test_fresh_can_resend(self, verification):
        with freeze_time(START):
            assert verification.can_resend()

    def test_daily_cap(self, verification):
        with freeze_time(START):
            for _ in range(EmailVerification.MAX_DAILY_RESENDS):
                assert verification.can_resend()
                verification.resend()
            assert not verification.can_resend()

    def test_cap_resets_after_midnight(self, verification):
        with freeze_time(START):
            for _ in range(EmailVerification.MAX_DAILY_RESENDS):
                verification.resend()
        with freeze_time(START + datetime.timedelta(minutes=15)):  # 00:05 next day
            assert verification.can_resend()
            verification.resend()
            verification.refresh_from_db()
            assert verification.resend_count == 1
            assert verification.last_resend_date == datetime.date(2026, 3, 2)

    def test_rotates_code_and_restarts_window(self, verification):
        old_code = verification.code
        later = START + datetime.timedelta(minutes=30)
        with freeze_time(later):
            assert not verification.is_valid()
            verification.resend()
            verification.refresh_from_db()
            assert verification.code != old_code
            assert verification.created_at == later
            assert verification.is_valid()
