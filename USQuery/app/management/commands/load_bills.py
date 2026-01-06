import asyncio
from django.core.management.base import BaseCommand
from app.utils import updateRecentBills, types

class Command(BaseCommand):
    help = "Load data from congress API into database"

    def handle(self, *args, **options):
        for t in types :
            asyncio.run(updateRecentBills(119, "!", t))
        self.stdout.write("Data load completed")
