"""Reconcile Apple subscriptions against the App Store Server API.

App Store Server Notifications are the primary sync mechanism, but Apple gives
up retrying after about three days. If the server was down for a deploy or a
notification was simply never delivered, a user can be left on a tier they no
longer pay for -- or worse, dropped off one they do.

This walks the subscriptions that are near or past their expiry (the window
where drift actually matters) and re-applies Apple's own view of them. It is
idempotent by construction: it goes through the same apply_state() reducer the
webhook uses, including the out-of-order guard.

Safe to run from cron, e.g. hourly.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from app import apple_iap
from app.models import AppleSubscription

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Re-syncs Apple subscriptions with the App Store Server API."

    def add_arguments(self, parser):
        parser.add_argument(
            '--window-hours',
            type=int,
            default=48,
            help='Also re-check subscriptions expiring within this many hours (default 48).',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Re-check every non-revoked subscription, ignoring the expiry window.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing anything.',
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() + timedelta(hours=options['window_hours'])

        qs = AppleSubscription.objects.filter(revoked_at__isnull=True).select_related('user')
        if not options['all']:
            qs = qs.filter(expires_date__lte=cutoff)

        total = qs.count()
        self.stdout.write(f"Checking {total} Apple subscription(s).")

        updated = 0
        skipped = 0
        failed = 0

        for subscription in qs:
            environment = apple_iap.environment_from_value(subscription.environment)
            state = apple_iap.fetch_subscription_state(
                subscription.original_transaction_id, environment
            )
            if state is None:
                failed += 1
                self.stderr.write(
                    f"Could not fetch state for {subscription.original_transaction_id}."
                )
                continue

            if options['dry_run']:
                self.stdout.write(
                    f"[dry-run] {subscription.original_transaction_id}: "
                    f"tier {subscription.tier} -> {state.get('tier')}, "
                    f"expires {subscription.expires_date} -> {state.get('period_end')}"
                )
                continue

            try:
                applied = apple_iap.apply_state(subscription.user, state)
            except Exception as exc:
                failed += 1
                logger.error("Failed to sync Apple subscription %s: %s",
                             subscription.original_transaction_id, exc, exc_info=True)
                self.stderr.write(f"Failed {subscription.original_transaction_id}: {exc}")
                continue

            if applied:
                updated += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Finished. Updated {updated}, skipped {skipped} (stale payload), failed {failed}."
        ))
