from django.core.management.base import BaseCommand
from django.db.models import Q
from BillQuery.models import Bill

EXPIRE_MAP = {
    0:  9,   # Introduced → Expired as Introduced
    10: 19,  # In origin committee → Expired in origin committee
    20: 28,  # Reported to origin floor → Expired on origin floor
    21: 27,  # Origin passed w/ amendment → Expired (awaiting outer concurrence)
    22: 27,  # Origin concurred w/ outer amendment → Expired before enrollment
    25: 29,  # Origin passed → Expired after origin passage
    30: 39,  # In outer committee → Expired in outer committee
    40: 48,  # Reported to outer floor → Expired on outer floor
    41: 47,  # Outer passed w/ amendment → Expired (awaiting origin concurrence)
    42: 47,  # Outer concurred w/ origin amendment → Expired before enrollment
    45: 49,  # Outer passed → Expired after outer passage
    **{sc: 59 for sc in range(50, 56)},  # Conference stages → Expired in conference
    60: 69,  # Enrolled/presented to president → Pocket vetoed
}

EXPIRE_FROM = set(EXPIRE_MAP.keys())


class Command(BaseCommand):
    help = 'Marks all non-terminal bills in the given congress as expired at end of congress'

    def add_arguments(self, parser):
        parser.add_argument('congress_num', type=int, help='Congress number (e.g. 118)')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would be updated without writing to the database'
        )

    def handle(self, *args, **options):
        congress_num = options['congress_num']
        dry_run = options['dry_run']
        n = congress_num

        bills = Bill.objects.filter(
            Q(id__gte=n * 100000,  id__lt=(n + 1) * 100000) |
            Q(id__gte=n * 1000000, id__lt=(n + 1) * 1000000),
            status_code__in=EXPIRE_FROM,
        )

        total = bills.count()
        self.stdout.write(
            f'Found {total} bill(s) to expire for congress {congress_num}'
            + (' (dry run)' if dry_run else '') + '.'
        )

        updated = 0
        for bill in bills.iterator(chunk_size=500):
            expired_sc = EXPIRE_MAP[bill.status_code]
            if dry_run:
                self.stdout.write(f'  {bill.id}: {bill.status_code} → {expired_sc}')
            else:
                bill.status_code = expired_sc
                bill.save(update_fields=['status_code'])
            updated += 1

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'Done. Expired {updated} bill(s).'))
        else:
            self.stdout.write(f'Dry run complete. {updated} bill(s) would be updated.')
