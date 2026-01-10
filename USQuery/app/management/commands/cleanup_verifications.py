from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from app.models import EmailVerification

class Command(BaseCommand):
    help = "Delete expired email verification records"

    def handle(self, *args, **kwargs):
        cutoff = timezone.now() - timedelta(minutes=10)
        deleted, _ = EmailVerification.objects.filter(
            created_at__lt=cutoff,
            user__is_active=False,
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted} expired verifications")
        )

