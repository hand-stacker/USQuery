from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from app.api.views import APP_VERSION_CACHE_KEY


class Command(BaseCommand):
    help = "Set the mobile app version string stored in Redis (never expires)."

    def add_arguments(self, parser):
        parser.add_argument("version", type=str, help="Version string, e.g. 1.2.3")

    def handle(self, *args, **options):
        version = options["version"].strip()
        if not version:
            raise CommandError("Version string cannot be empty.")
        cache.set(APP_VERSION_CACHE_KEY, version, timeout=None)
        self.stdout.write(self.style.SUCCESS(f"App version set to: {version}"))
