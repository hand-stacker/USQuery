import uuid
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import timedelta


DEVICE_LIMITS = {
    0:20, # this is just for my alpha test, update later
    1:10,
    2:10,
    3:1000}

STARRED_BILLS_LIMITS = {
    0:10,
    1:100,
    2:1000,
    3:1000}

STARRED_MEMBERSHIPS_LIMITS = {
    0:5,
    1:100,
    2:1000,
    3:1000}

PREDICTION_LIMITS = {
    0:5,
    1:100,
    2:1000,
    3:1000000}

class UserProfile(models.Model):
    class SubType(models.IntegerChoices):
        Free = 0
        Plus = 1
        Premium = 2
        Special = 3

    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.IntegerField(choices=SubType, default=0)
    enabled_bill_notif = models.BooleanField(default=True)
    enabled_subject_notif = models.BooleanField(default=True)
    scheduled_for_deletion = models.BooleanField(default=False, db_index=True)

    def get_active_devices(self):
        return self.devices.filter(is_active=True)

    def get_starred_bills(self):
        return self.starred_bills.filter(is_active=True)

    def get_starred_memberships(self):
        return self.starred_memberships.filter(is_active=True)

    # gets active subjects
    def get_favorite_subjects(self):
        return self.favorite_subjects.filter(is_active=True)

    # returns the device limit (int) for this user_profile
    def get_device_limit(self):
        return DEVICE_LIMITS[self.user_type]

    # returns the starred bills limit (int) for this user_profile
    def get_starred_bills_limit(self):
        return STARRED_BILLS_LIMITS[self.user_type]

    # returns the starred memberships limit (int) for this user_profile
    def get_starred_memberships_limit(self):
        return STARRED_MEMBERSHIPS_LIMITS[self.user_type]

    # for future use, limits daily prediction views
    def get_predicton_limit(self):
        return PREDICTION_LIMITS[self.user_type]




class EmailVerification(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    code = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    resend_count = models.PositiveIntegerField(default=0)
    last_resend_date = models.DateField(null=True, blank=True)

    MAX_DAILY_RESENDS = 5

    def is_valid(self):
        return timezone.now() <= self.created_at + timedelta(minutes=10)

    def can_resend(self):
        today = timezone.localdate()

        if self.last_resend_date != today:
            return True

        return self.resend_count < self.MAX_DAILY_RESENDS

    def resend(self):
        today = timezone.localdate()

        if self.last_resend_date != today:
            self.resend_count = 0
            self.last_resend_date = today

        self.resend_count += 1
        self.code = uuid.uuid4()
        self.created_at = timezone.now()

        self.save(
            update_fields=[
                "code",
                "created_at",
                "resend_count",
                "last_resend_date",
            ]
        )