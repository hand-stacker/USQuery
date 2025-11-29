import aiohttp, asyncio
from django.core.cache import cache
from app.utils import make_cache_keyASYNC, connectASYNC, types, getSummaryAI
from USQuery import settings

timeout_day = 60 * 60 * 24
## ASYNC : Special async caching func for bill summaries, returns {"_id" : <int>, "AI_generated_content?" : <bool>, "summary" : <text> }
async def fetch_summary(session, congress_id, bill_type, num):
    context = {}
    if (int(num) < 10000):
        _id = int(congress_id) * 100000 + types[bill_type] * 10000 + int(num)
    else :
        _id = int(congress_id) * 1000000 + types[bill_type] * 100000 + int(num)
    context["_id"] = _id
    context['AI_generated_content?'] = False

    apiURL = settings.CONGRESS_DIR + "bill/" + str(congress_id) + "/" + bill_type + "/" + str(num)
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

async def batch_load_summaries(args):
    session = aiohttp.ClientSession()
    tasks = [fetch_summary(session, arg[0], arg[1], arg[2]) for arg in args]
    results = await asyncio.gather(*tasks)
    await session.close()
    return {blob["_id"]: blob for blob in results}