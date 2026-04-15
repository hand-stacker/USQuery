import aiohttp, asyncio
from django.core.cache import cache
from app.utils import make_cache_keyASYNC, connectASYNC, types, getSummaryAI
from USQuery import settings

timeout_day = 60 * 60 * 24
def _truncate(text, max_len = 240):
    s = str(text or "")
    if len(s) <= max_len:
        return s
    cut = max_len - 3
    idx = s.rfind(' ', 0, cut)
    if idx == -1:
        return s[:cut] + '...'
    return s[:idx] + '...'
## ASYNC : Special async caching func for bill summaries, returns {"_id" : <int>, "AI_generated_content?" : <bool>, "summary" : <text> }
async def fetch_summary(session, bill, try_AI_fetch=True, truncate = False):
    context = {}
    _id = bill.id
    context["_id"] = _id
    context['AI_generated_content?'] = False
    context['summary'] = "We cannot provide a summary at this time."

    apiURL = settings.CONGRESS_DIR + "bill/" + bill.getURL()
    header_str = '?api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=250'
    fullpath = apiURL + '/summaries'
    key = await make_cache_keyASYNC(fullpath, header_str)
    cached = await cache.aget(key)
    if cached:
        context["summary"] = cached
        if truncate:
            context["summary"] = _truncate(context["summary"])
        return context
    data = await connectASYNC(session, fullpath, header_str)
    if (data != ''):
        if (len(data['summaries']) < 1):
            if (try_AI_fetch) :
                context['AI_generated_content?'] = True
                context['summary'] = await getSummaryAI(session, apiURL + "/text", header_str, _id)
        else :
            context['summary'] = data['summaries'][0]['text']
    if not context["AI_generated_content?"]: await cache.aset(key, context["summary"], timeout_day)
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
    key = await make_cache_keyASYNC(fullpath, header_str)
    cached = await cache.aget(key)
    if cached:
        context["actions"] = cached
        return context
    data = await connectASYNC(session, fullpath, header_str)
    context['actions'] = data['actions']
    await cache.aset(key, context["actions"], timeout_day)
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