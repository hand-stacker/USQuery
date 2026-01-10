import uuid
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import timedelta

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)



class EmailVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    code = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    resend_count = models.PositiveIntegerField(default=0)
    last_resend_date = models.DateField(null=True, blank=True)

    def is_valid(self):
        return timezone.now() <= self.created_at + timedelta(minutes=10)

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

    def can_resend(self):
            today = timezone.localdate()

            if self.last_resend_date != today:
                return True

            return self.resend_count < self.MAX_DAILY_RESENDS

class EmailVerification(models.Model):
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