import asyncio
from datetime import datetime, timezone

from django.core.cache import cache
from django.core.management.base import BaseCommand

from app.models import UserProfile
from notifications.push import send_floor_notification

# Maps common timezone abbreviations to their UTC offsets in hours.
# Users who store "PST" are always treated as UTC-8 regardless of DST.
_TZ_OFFSETS = {
    'UTC': 0, 'GMT': 0,
    'EST': -5, 'EDT': -4,
    'CST': -6, 'CDT': -5,
    'MST': -7, 'MDT': -6,
    'PST': -8, 'PDT': -7,
    'AKST': -9, 'AKDT': -8,
    'HST': -10,
    'AST': -4,
}


def _local_to_utc_hour(local_hour: int, tz_abbr: str) -> int:
    offset = _TZ_OFFSETS.get((tz_abbr or 'UTC').upper(), 0)
    return (local_hour - offset) % 24


class Command(BaseCommand):
    help = (
        "Send daily floor notifications to users whose preferred local time matches "
        "the current UTC hour. Schedule this command to run every hour. "
        "Note: load_bills runs approximately every 3 hours and may fire multiple times per day."
    )

    def handle(self, *args, **options):
        now = datetime.now(timezone.utc)
        current_utc_hour = now.hour
        today_str = now.date().isoformat()

        house_cache  = cache.get("floor_notif_house")
        senate_cache = cache.get("floor_notif_senate")

        house_ids = (
            house_cache["bill_ids"]
            if house_cache and house_cache.get("date") == today_str
            else []
        )
        senate_ids = (
            senate_cache["bill_ids"]
            if senate_cache and senate_cache.get("date") == today_str
            else []
        )

        if house_ids:
            profiles = list(
                UserProfile.objects.filter(
                    enabled_house_floor_notif=True,
                    house_floor_notif_frequency=UserProfile.FloorNotifFrequency.DAILY,
                    house_floor_notif_time__isnull=False,
                    house_floor_notif_timezone__isnull=False,
                ).values_list("id", "house_floor_notif_time", "house_floor_notif_timezone")
            )
            matching_ids = [
                pid for pid, local_hour, tz in profiles
                if _local_to_utc_hour(local_hour, tz) == current_utc_hour
            ]
            if matching_ids:
                asyncio.run(send_floor_notification("house", house_ids, matching_ids))
                self.stdout.write(f"Sent house floor notifications to {len(matching_ids)} users.")

        if senate_ids:
            profiles = list(
                UserProfile.objects.filter(
                    enabled_senate_floor_notif=True,
                    senate_floor_notif_frequency=UserProfile.FloorNotifFrequency.DAILY,
                    senate_floor_notif_time__isnull=False,
                    senate_floor_notif_timezone__isnull=False,
                ).values_list("id", "senate_floor_notif_time", "senate_floor_notif_timezone")
            )
            matching_ids = [
                pid for pid, local_hour, tz in profiles
                if _local_to_utc_hour(local_hour, tz) == current_utc_hour
            ]
            if matching_ids:
                asyncio.run(send_floor_notification("senate", senate_ids, matching_ids))
                self.stdout.write(f"Sent senate floor notifications to {len(matching_ids)} users.")

        self.stdout.write("Floor notification dispatch complete.")
