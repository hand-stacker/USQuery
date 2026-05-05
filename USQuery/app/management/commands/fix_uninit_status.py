import asyncio
import aiohttp
from django.core.management.base import BaseCommand
from django.db.models import Q
from BillQuery.models import Bill
from app.utils import compute_status_code, compute_history_flags, getAllActionCodes, connectASYNC
from USQuery import settings


# run with something like 'python manage.py fix_uninit_status 119 --batch-size 50'
class Command(BaseCommand):
    help = 'Computes status_code and history flags for bills with status_code=-1 in the given congress'

    def add_arguments(self, parser):
        parser.add_argument('congress_num', type=int, help='Congress number (e.g. 119)')
        parser.add_argument('--batch-size', type=int, default=100, help='Number of bills to process per batch (default: 100)')

    def handle(self, *args, **options):
        congress_num = options['congress_num']
        batch_size = options['batch_size']
        updated, errors = asyncio.run(self._run(congress_num, batch_size))
        self.stdout.write(self.style.SUCCESS(
            f'Done. Updated {updated} bill(s), {errors} error(s).'
        ))

    async def _run(self, congress_num, batch_size):
        n = congress_num
        MAX = 1000
        bills = Bill.objects.filter(
            Q(id__gte=n * 100000,  id__lt=(n + 1) * 100000) |
            Q(id__gte=n * 1000000, id__lt=(n + 1) * 1000000),
            status_code=-1
        )
        total = await bills.acount()
        self.stdout.write(
            f'Found {total} uninitialized bill(s) for congress {congress_num}'
            + (f', processing first {MAX}.' if total > MAX else '.')
        )

        header_str = '&api_key=' + settings.CONGRESS_KEY + '&format=json&limit=250'
        updated = errors = 0

        async with aiohttp.ClientSession() as session:
            async for bill in bills.aiterator(chunk_size=batch_size):
                if updated + errors >= MAX:
                    break
                url = (
                    settings.CONGRESS_DIR
                    + 'bill/' + str(congress_num)
                    + '/' + bill.getTypeURL()
                    + '/' + str(bill.getNum())
                    + '/actions?'
                )
                try:
                    initial = await connectASYNC(session, url, header_str)
                    if not initial:
                        raise ValueError('empty response')
                    action_codes = await getAllActionCodes(session, header_str, initial)
                except Exception as e:
                    self.stderr.write(f'  Error fetching actions for bill {bill.id}: {e}')
                    errors += 1
                    continue

                new_sc = await compute_status_code(bill.getOriginCode(), action_codes)
                new_veto, new_conf = compute_history_flags(action_codes)

                bill.status_code = new_sc
                bill.veto_in_history = new_veto
                bill.conf_in_history = new_conf
                await bill.asave(update_fields=['status_code', 'veto_in_history', 'conf_in_history'])
                self.stdout.write(
                    f'  {bill.id}: sc={new_sc} veto={new_veto} conf={new_conf}'
                )
                updated += 1

        return updated, errors
