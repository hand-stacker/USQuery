from django.db import models

class Device(models.Model):
    device_token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=10)  # ios | android
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.device_token[:12]


class StarredBill(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="stars")
    bill_id = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("device", "bill_id")

    def __str__(self):
        return f"{self.device} - {self.bill_id}"
