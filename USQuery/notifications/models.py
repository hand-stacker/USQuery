import datetime
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.fields import related

from app.models import UserProfile

class Device(models.Model):
    id = models.BigAutoField(primary_key=True)
    user_profile = models.ForeignKey(
        "app.UserProfile",
        on_delete=models.CASCADE,
        related_name="devices",
        blank=False,
        #for now set to True so database accepts it
        null=True,
    )
    device_token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=10)  # ios | android
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    # use this to automatically set is_active to false
    # when a devices is last used in a very long time...
    last_used = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.device_token[:12]

    def clean(self):
        super().clean()
        if not self.user_profile:
            return

        qs = Device.objects.filter(user_profile=self.user_profile, is_active=True)
        if self.id:
            qs = qs.exclude(id=self.id)

        device_limit = self.user_profile.get_device_limit()
        if qs.count() >= device_limit:
            raise ValidationError(message="You can have at most " + str(device_limit) + " devices on your account.", code="DeviceLimit")

    def save(self, *args, **kwargs):
        # enforce validation (including max-3 check)
        self.full_clean()
        super().save(*args, **kwargs)

    # every once in a while delete inactive devices from database
    def deactivate(self):
        self.is_active = False
        super.save()

    def refresh_last_used(self):
        self.last_used=datetime.datetime.now()
        super.save()

    class Meta:
        ordering = ["device_token", "user_profile"]


class StarredBill(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name = "starred_bills",blank=True, null=True)
    bill_id = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user_profile", "bill_id")

    def __str__(self):
        return f"{self.user_profile} - {self.bill_id}"
