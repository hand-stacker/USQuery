import aiohttp, asyncio
from django.core.cache import cache
from app.utils import connectASYNC, types, merge_fastpath_votes
from BillQuery.models import BillSummary
from USQuery import settings

timeout_day = 60 * 60 * 24
## key prefixes for derived (non-raw-API) cached values; raw API JSON lives under
## connect_and_cacheASYNC's url-hash keys and must never share keys with these
SUMMARY_TEXT_KEY = 'summary_text:'
ACTIONS_LIST_KEY = 'actions_list:'
_UNUSABLE_SUMMARIES = {"We cannot provide a summary at this time.", "__BILL_TOO_LARGE__"}

def _truncate(text, max_len = 240):
    s = str(text or "")
    if len(s) <= max_len:
        return s
    cut = max_len - 3
    idx = s.rfind(' ', 0, cut)
    if idx == -1:
        return s[:cut] + '...'
    return s[:idx] + '...'

## ASYNC : Special async caching func for bill summaries.
## Returns {"_id": int, "AI_generated_content?": bool, "summary": str, "generated_at": date|None}
## AI generation is never triggered here — use the web endpoint for that.
async def fetch_summary(session, bill, try_AI_fetch=False, truncate=False):
    context = {}
    _id = bill.id
    context["_id"] = _id
    context['AI_generated_content?'] = False
    context['summary'] = "We cannot provide a summary at this time."
    context['generated_at'] = None

    apiURL = settings.CONGRESS_DIR + "bill/" + bill.getURL()
    header_str = '?api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=250'
    fullpath = apiURL + '/summaries'
    key = SUMMARY_TEXT_KEY + str(_id)
    cached = await cache.aget(key)
    if cached:
        context["summary"] = cached
        if truncate:
            context["summary"] = _truncate(context["summary"])
        return context
    data = await connectASYNC(session, fullpath, header_str)
    if data != '':
        if len(data['summaries']) < 1:
            # No Congress summary: serve any stored AI summary from DB
            try:
                bill_summary = await BillSummary.objects.aget(id=_id)
                if bill_summary.summary and bill_summary.summary.strip() and bill_summary.summary not in _UNUSABLE_SUMMARIES:
                    context['AI_generated_content?'] = True
                    context['summary'] = bill_summary.summary
                    context['generated_at'] = bill_summary.generated_at
            except BillSummary.DoesNotExist:
                pass
        else:
            context['summary'] = data['summaries'][0]['text']
    if not context["AI_generated_content?"]:
        await cache.aset(key, context["summary"], timeout_day)
    if truncate:
        context["summary"] = _truncate(context["summary"])
    return context

async def fetch_actions(session, bill):
    context = {}
    _id = bill.id
    context["_id"] = _id
    apiURL = settings.CONGRESS_DIR + "bill/" + bill.getURL()
    header_str = '?api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=250'
    fullpath = apiURL + '/actions'
    key = ACTIONS_LIST_KEY + str(_id)
    cached = await cache.aget(key)
    if cached is not None:
        context["actions"] = cached if isinstance(cached, list) else []
        return context
    data = await connectASYNC(session, fullpath, header_str)
    actions = data.get('actions', []) if data else []
    context['actions'] = actions if isinstance(actions, list) else []
    await cache.aset(key, context["actions"], timeout_day)
    context['actions'] = await merge_fastpath_votes(bill, context['actions'])
    return context

async def batch_load_summaries(args, truncate = False):
    n = len(args)
    results = [None] * n
    limit = 5

    async with aiohttp.ClientSession() as session:
        sem = asyncio.Semaphore(limit)

        async def _worker(idx, bill):
            async with sem:
                ## fetch summary without calling AI API in order to limit token usage and make sure bandwith is fast
                results[idx] = await fetch_summary(session, bill, False, truncate)

        async with asyncio.TaskGroup() as tg:
            for i, bill in enumerate(args):
                tg.create_task(_worker(i, bill))

    return {blob["_id"]: blob for blob in results}


async def batch_load_actions(args):
    n = len(args)
    results = [None] * n
    limit = 5

    async with aiohttp.ClientSession() as session:
        sem = asyncio.Semaphore(limit)

        async def _worker(idx, bill):
            async with sem:
                results[idx] = await fetch_actions(session, bill)

        async with asyncio.TaskGroup() as tg:
            for i, bill in enumerate(args):
                tg.create_task(_worker(i, bill))

    return {blob["_id"]: blob for blob in results}