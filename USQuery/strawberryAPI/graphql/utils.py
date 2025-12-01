import aiohttp, asyncio
from django.core.cache import cache
from app.utils import make_cache_keyASYNC, connectASYNC, types, getSummaryAI
from USQuery import settings

timeout_day = 60 * 60 * 24
## ASYNC : Special async caching func for bill summaries, returns {"_id" : <int>, "AI_generated_content?" : <bool>, "summary" : <text> }
async def fetch_summary(session, bill):
    context = {}
    _id = bill.id
    context["_id"] = _id
    context['AI_generated_content?'] = False

    apiURL = settings.CONGRESS_DIR + "bill/" + bill.getURL()
    header_str = '?api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=250'
    fullpath = apiURL + '/summaries'
    key = await make_cache_keyASYNC(fullpath, header_str)
    cached = cache.get(key)
    if cached:
        context["summary"] = cached
        return context
    data = await connectASYNC(session, fullpath, header_str)
    if (data != ''):
        if (len(data['summaries']) < 1):
            context['AI_generated_content?'] = True
            context['summary'] = await getSummaryAI(session, apiURL + "/text", header_str, _id)
        else :
            context['summary'] = data['summaries'][0]['text']
    if not context["AI_generated_content?"]: cache.set(key, context["summary"], timeout_day)
    return context

async def fetch_actions(session, bill):
    context = {}
    _id = bill.id
    context["_id"] = _id
    apiURL = settings.CONGRESS_DIR + "bill/" + bill.getURL()
    header_str = '?api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=250'
    fullpath = apiURL + '/actions'
    key = await make_cache_keyASYNC(fullpath, header_str)
    cached = cache.get(key)
    if cached:
        context["actions"] = cached
        return context
    data = await connectASYNC(session, fullpath, header_str)
    context['actions'] = data['actions']
    cache.set(key, context["actions"], timeout_day)
    return context

async def batch_load_summaries(args):
    session = aiohttp.ClientSession()
    tasks = [fetch_summary(session, arg) for arg in args]
    results = await asyncio.gather(*tasks)
    await session.close()
    return {blob["_id"]: blob for blob in results}


async def batch_load_actions(args):
    session = aiohttp.ClientSession()
    tasks = [fetch_actions(session, arg) for arg in args]
    results = await asyncio.gather(*tasks)
    await session.close()
    return {blob["_id"]: blob for blob in results}