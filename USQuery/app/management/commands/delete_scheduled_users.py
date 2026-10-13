import logging

import stripe
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import UserProfile
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


def _cancel_stripe_subscription(profile):
    """Immediately cancel the profile's Stripe subscription, if any, before the
    account is deleted so we stop billing a user whose account is going away.

    Cancellation is best-effort: a Stripe failure is logged but must not block the
    account deletion. Uses immediate cancellation (not cancel_at_period_end) since
    there will be no account left to use the remaining paid time.
    """
    sub_id = getattr(profile, "stripe_subscription_id", None)
    if not sub_id:
        return
    if not getattr(settings, "STRIPE_SECRET_KEY", None):
        logger.warning("Cannot cancel subscription %s: STRIPE_SECRET_KEY not configured.", sub_id)
        return
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.Subscription.cancel(sub_id)
    except Exception as ex:
        logger.warning("Failed to cancel Stripe subscription %s before account deletion: %s", sub_id, ex)


def _note_apple_subscription(profile):
    """Log an App Store subscription that will outlive the account.

    Apple subscriptions cannot be cancelled server-side -- there is no API for
    it, only the user's Apple ID settings. Deleting the account therefore stops
    us honoring the subscription but does NOT stop Apple billing for it, so log
    loudly rather than letting it disappear silently.
    """
    original_transaction_id = getattr(profile, "apple_original_transaction_id", None)
    if not original_transaction_id:
        return
    logger.warning(
        "User %s is being deleted with an active App Store subscription (%s). "
        "Apple will keep billing until the user cancels at %s.",
        profile.user_id, original_transaction_id,
        "https://apps.apple.com/account/subscriptions",
    )


class Command(BaseCommand):
    help = "Deletes users whose UserProfile.scheduled_for_deletion is True."

    def handle(self, *args, **options):
        qs = UserProfile.objects.filter(scheduled_for_deletion=True)
        total = qs.count()
        self.stdout.write(f"Found {total} user profile(s) scheduled for deletion.")
        deleted_count = 0

        for profile in qs.select_related('user'):
            _cancel_stripe_subscription(profile)
            _note_apple_subscription(profile)
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