import asyncio
from django.core.cache import cache
from django.core.management.base import BaseCommand
from app.utils import updateRecentBills, types
from notifications.push import send_subject_notification

class Command(BaseCommand):
    help = "Load data from congress API into database"
    
    def handle(self, *args, **options):
        self.stdout.write("start load")
        for t in types :
            asyncio.run(updateRecentBills(119, "!", t))
        subjects = cache.get("bill_subjects", set())
        asyncio.run(send_subject_notification(
            subjects=subjects,
            title="New actions on bills you might be interested in.",
            body="New actions were made on bills related to your favorite subjects."
        ))
        cache.delete("bill_subjects")
        self.stdout.write("Data load completed")
