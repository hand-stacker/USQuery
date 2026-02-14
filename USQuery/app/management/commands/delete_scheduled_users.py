from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import UserProfile
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = "Deletes users whose UserProfile.scheduled_for_deletion is True."

    def handle(self, *args, **options):
        qs = UserProfile.objects.filter(scheduled_for_deletion=True)
        total = qs.count()
        self.stdout.write(f"Found {total} user profile(s) scheduled for deletion.")
        deleted_count = 0

        for profile in qs.select_related('user'):
            user = getattr(profile, "user", None)
            if user:
                username = getattr(user, "username", str(user.pk))
                try:
                    user.delete()
                    deleted_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Deleted user {username} (and cascaded related data)."))
                except Exception as ex:
                    self.stderr.write(f"Failed to delete user {username}: {ex}")
            else:
                # If profile exists with no user, delete the profile itself
                try:
                    profile.delete()
                    self.stdout.write(self.style.WARNING(f"Deleted orphaned profile id={profile.pk}."))
                except Exception as ex:
                    self.stderr.write(f"Failed to delete orphaned profile id={profile.pk}: {ex}")

        self.stdout.write(self.style.SUCCESS(f"Finished. Deleted {deleted_count} user(s)."))