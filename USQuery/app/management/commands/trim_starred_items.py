from django.core.management.base import BaseCommand
from app.models import UserProfile
from notifications.models import StarredBill, StarredMembership


class Command(BaseCommand):
    help = "Deactivates starred items that exceed a user's current tier limits (run monthly after downgrades)."

    def handle(self, *args, **options):
        trimmed_bills = 0
        trimmed_members = 0

        for profile in UserProfile.objects.all():
            bill_limit = profile.get_starred_bills_limit()
            member_limit = profile.get_starred_memberships_limit()

            active_bills = profile.get_starred_bills().order_by('created_at')
            excess_bills = active_bills.count() - bill_limit
            if excess_bills > 0:
                oldest_ids = list(active_bills.values_list('id', flat=True)[:excess_bills])
                StarredBill.objects.filter(id__in=oldest_ids).update(is_active=False)
                trimmed_bills += excess_bills

            active_members = profile.get_starred_memberships().order_by('created_at')
            excess_members = active_members.count() - member_limit
            if excess_members > 0:
                oldest_ids = list(active_members.values_list('id', flat=True)[:excess_members])
                StarredMembership.objects.filter(id__in=oldest_ids).update(is_active=False)
                trimmed_members += excess_members

        self.stdout.write(self.style.SUCCESS(
            f"Trimmed {trimmed_bills} bill(s) and {trimmed_members} membership(s) to match tier limits."
        ))
