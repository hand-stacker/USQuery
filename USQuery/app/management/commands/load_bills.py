import asyncio
from datetime import date
from django.core.cache import cache
from django.core.management.base import BaseCommand
from app import utils as app_utils
from app.utils import updateRecentBills, types
from app.models import UserProfile
from BillQuery.models import Bill
from notifications.push import send_subject_notification, send_floor_notification

class Command(BaseCommand):
    help = "Load data from congress API into database"

    def handle(self, *args, **options):
        self.stdout.write("start load")
        app_utils._house_bill_ids_this_run.clear()
        app_utils._senate_bill_ids_this_run.clear()
        for t in types:
            asyncio.run(updateRecentBills(119, "!", t))

        # Fast-path House/Senate vote checks -- must run before the
        # _house_bill_ids_this_run / _senate_bill_ids_this_run sets are read below,
        # since they populate the same module-level sets that updateRecentBills does.
        asyncio.run(app_utils.checkHouseVotes())
        asyncio.run(app_utils.checkSenateVotes())

        today = date.today()
        today_str = today.isoformat()
        new_house_ids  = list(app_utils._house_bill_ids_this_run)
        new_senate_ids = list(app_utils._senate_bill_ids_this_run)

        # Filter to bills whose latest action is today — suppresses notifications
        # from API backfill of older actions.
        notif_house_ids = list(
            Bill.objects.filter(id__in=new_house_ids, latest_action=today).values_list("id", flat=True)
        )
        notif_senate_ids = list(
            Bill.objects.filter(id__in=new_senate_ids, latest_action=today).values_list("id", flat=True)
        )

        if notif_house_ids:
            house_cache = cache.get("floor_notif_house")
            if house_cache and house_cache.get("date") == today_str:
                all_house_ids = list(set(house_cache["bill_ids"]) | set(notif_house_ids))
            else:
                all_house_ids = notif_house_ids
            cache.set("floor_notif_house", {"date": today_str, "bill_ids": all_house_ids}, timeout=None)
            consistent_ids = list(
                UserProfile.objects.filter(
                    enabled_house_floor_notif=True,
                    house_floor_notif_frequency=UserProfile.FloorNotifFrequency.CONSISTENT,
                ).values_list("id", flat=True)
            )
            if consistent_ids:
                asyncio.run(send_floor_notification("house", notif_house_ids, consistent_ids))

        if notif_senate_ids:
            senate_cache = cache.get("floor_notif_senate")
            if senate_cache and senate_cache.get("date") == today_str:
                all_senate_ids = list(set(senate_cache["bill_ids"]) | set(notif_senate_ids))
            else:
                all_senate_ids = notif_senate_ids
            cache.set("floor_notif_senate", {"date": today_str, "bill_ids": all_senate_ids}, timeout=None)
            consistent_ids = list(
                UserProfile.objects.filter(
                    enabled_senate_floor_notif=True,
                    senate_floor_notif_frequency=UserProfile.FloorNotifFrequency.CONSISTENT,
                ).values_list("id", flat=True)
            )
            if consistent_ids:
                asyncio.run(send_floor_notification("senate", notif_senate_ids, consistent_ids))

        subjects = cache.get("bill_subjects", set())
        asyncio.run(send_subject_notification(
            subjects=subjects,
            title="New actions on bills you might be interested in.",
            body="New actions were made on bills related to your favorite subjects."
        ))
        cache.delete("bill_subjects")
        self.stdout.write("Data load completed")
