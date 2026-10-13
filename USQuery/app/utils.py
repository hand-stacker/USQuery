from datetime import datetime, date, timedelta, timezone as dt_timezone
from asgiref.sync import sync_to_async
from django.core.cache import cache
import requests, asyncio, json, aiohttp, hashlib, re, time
from requests.exceptions import HTTPError
from USQuery import settings
from SenateQuery.models import Member, Congress, Membership
from BillQuery.models import Bill, Vote, BillSummary, Subject, US_EASTERN
from notifications.push import send_bill_notification
from collections import defaultdict
from xml.etree import cElementTree as ET
import anthropic
from django.db.models import Q, Count, Prefetch, Max
from bs4 import BeautifulSoup

## Raised when the Congress API does not return the core data a bill page needs
## (upstream slow/down). Callers should degrade to a friendly "try again" page
## rather than letting a None subscript become a 500 / worker timeout.
class BillUpstreamUnavailable(Exception):
    pass

## helpful objects that map state related data
timeout_day = 60 * 60 * 24
current_congress = 119
state_list = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
              'HI','ID','IN','IL','IA','KS','KY','LA','ME','MD',
              'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
              'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
              'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']
state_dict = {'AL' : 'Alabama', 'AK' : 'Alaska', 'AZ' : 'Arizona', 'AR' : 'Arkansas',
              'CA' : 'California', 'CO' : 'Colorado', 'CT' : 'Connecticut',
              'DE' : 'Delaware', 'FL' : 'Florida', 'GA' : 'Georgia', 'HI' : 'Hawaii',
              'ID' : 'Idaho', 'IN' : 'Indiana', 'IL' : 'Illinois', 'IA' : 'Iowa',
              'KS' : 'Kansas', 'KY' : 'Kentucky', 'LA' : 'Louisiana', 'ME' : 'Maine',
              'MD' : 'Maryland', 'MA' : 'Massachusetts', 'MI' : 'Michigan',
              'MN' : 'Minnesota', 'MS' : 'Mississippi', 'MO' : 'Missouri', 'MT' : 'Montana',
              'NE' : 'Nebraska', 'NV' : 'Nevada', 'NH' : 'New Hampshire', 'NJ' : 'New Jersey',
              'NM' : 'New Mexico', 'NY' : 'New York', 'NC' : 'North Carolina',
              'ND' : 'North Dakota', 'OH' : 'Ohio', 'OK' : 'Oklahoma', 'OR' : 'Oregon',
              'PA' : 'Pennsylvania', 'RI' : 'Rhode Island', 'SC' : 'South Carolina',
              'SD' : 'South Dakota', 'TN' : 'Tennessee', 'TX' : 'Texas', 'UT' : 'Utah',
              'VT' : 'Vermont', 'VA' : 'Virginia', 'WA' : 'Washington', 'WV' : 'West Virginia',
              'WI' : 'Wisconsin', 'WY' : 'Wyoming',
              'DC' : 'District of Columbia', 'AS' : 'American Samoa', 'GU' : 'Guam',
              'MP' : 'Northern Mariana Islands', 'PR' : 'Puerto Rico', 'VI' : 'Virgin Islands'
              }
reverse_state_dict = {'Alabama' : 'AL', 'Alaska' : 'AK', 'Arizona' : 'AZ', 'Arkansas' : 'AR',
              'California' : 'CA', 'Colorado' : 'CO', 'Connecticut' : 'CT', 'Delaware' : 'DE',
              'Florida' : 'FL', 'Georgia' : 'GA', 'Hawaii' : 'HI', 'Idaho' : 'ID',
              'Indiana' : 'IN', 'Illinois' : 'IL', 'Iowa' : 'IA', 'Kansas' : 'KS',
              'Kentucky' : 'KY', 'Louisiana' : 'LA', 'Maine' : 'ME', 'Maryland' : 'MD',
              'Massachusetts' : 'MA', 'Michigan' : 'MI', 'Minnesota' : 'MN',
              'Mississippi' : 'MS', 'Missouri' : 'MO', 'Montana' : 'MT', 'Nebraska' : 'NE',
              'Nevada' : 'NV', 'New Hampshire' : 'NH', 'New Jersey' : 'NJ', 'New Mexico' : 'NM',
              'New York' : 'NY', 'North Carolina' : 'NC', 'North Dakota' : 'ND', 'Ohio' : 'OH',
              'Oklahoma' : 'OK', 'Oregon' : 'OR', 'Pennsylvania' : 'PA', 'Rhode Island' : 'RI',
              'South Carolina' : 'SC', 'South Dakota' : 'SD', 'Tennessee' : 'TN', 'Texas' : 'TX',
              'Utah' : 'UT', 'Vermont' : 'VT', 'Virginia' : 'VA', 'Washington' : 'WA',
              'West Virginia' : 'WV', 'Wisconsin' : 'WI', 'Wyoming' : 'WY',
              'District of Columbia' : 'DC', 'American Samoa' : 'AS', 'Guam' : 'GU',
              'Northern Mariana Islands' : 'MP', 'Puerto Rico' : 'PR', 'Virgin Islands' : 'VI'
              }
state_fips = {
    'AL': '01', 'AK': '02', 'AZ': '04', 'AR': '05', 'CA': '06',
    'CO': '08', 'CT': '09', 'DE': '10', 'FL': '12', 'GA': '13',
    'HI': '15', 'ID': '16', 'IL': '17', 'IN': '18', 'IA': '19',
    'KS': '20', 'KY': '21', 'LA': '22', 'ME': '23', 'MD': '24',
    'MA': '25', 'MI': '26', 'MN': '27', 'MS': '28', 'MO': '29',
    'MT': '30', 'NE': '31', 'NV': '32', 'NH': '33', 'NJ': '34',
    'NM': '35', 'NY': '36', 'NC': '37', 'ND': '38', 'OH': '39',
    'OK': '40', 'OR': '41', 'PA': '42', 'RI': '44', 'SC': '45',
    'SD': '46', 'TN': '47', 'TX': '48', 'UT': '49', 'VT': '50',
    'VA': '51', 'WA': '53', 'WV': '54', 'WI': '55', 'WY': '56',
    'DC': '11', 'AS': '60', 'GU': '66', 'MP': '69', 'PR': '72', 'VI': '78'
}
fips_to_count = {
    '01' : 0, '02' : 1, '04' : 2, '05' : 3, '06' : 4,
    '08' : 5, '09' : 6, '10' : 7, '12' : 8, '13'  :9,
    '15' : 10, '16' : 11, '17'  :12, '18' : 13, '19' : 14,
    '20' : 15, '21' : 16, '22' : 17, '23' : 18, '24' : 19,
    '25' : 20, '26' : 21, '27' : 22, '28' : 23, '29' : 24,
    '30' : 25, '31' : 26, '32' : 27, '33' : 28, '34' : 29,
    '35' : 30, '36' : 31, '37' : 32, '38' : 33, '39' : 34,
    '40' : 35, '41' : 36, '42' : 37, '44' : 38, '45' : 39,
    '46' : 40, '47' : 41, '48' : 42, '49' : 43, '50' : 44,
    '51' : 45, '53' : 46, '54' : 47, '55' : 48, '56' : 49,
    '11' : None, '60' : None, '66' : None, '69' : None, '72' : None, '78' : None
}
## maps a bill type to numerical code in project
types = {
            's' : 0,
            'sres' : 1,
            'sjres' : 2,
            'sconres' : 3,
            'hr' : 4,
            'hres' : 5,
            'hjres' : 6,
            'hconres' : 7}

SENATE_TYPES = frozenset({'s', 'sres', 'sjres', 'sconres'})
HOUSE_TYPES  = frozenset({'hr', 'hres', 'hjres', 'hconres'})

# Accumulates bill IDs that received new actions during the current load_bills run.
# Cleared and read by load_bills.py before/after calling updateRecentBills.
_senate_bill_ids_this_run: set = set()
_house_bill_ids_this_run: set = set()

month_to_num = {'Jan' : '01',
                'Feb' : '02',
                'Mar' : '03',
                'Apr' : '04',
                'May' : '05',
                'Jun' : '06',
                'Jul' : '07',
                'Aug' : '08',
                'Sep' : '09',
                'Sept' : '09',
                'Oct' : '10',
                'Nov' : '11',
                'Dec' : '12'}

## Helpful function for making a xml tree into a dictionary. Source : https://stackoverflow.com/a/10077069
def etree_to_dict(t):
    d = {t.tag: {} if t.attrib else None}
    children = list(t)
    if children:
        dd = defaultdict(list)
        for dc in map(etree_to_dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        d = {t.tag: {k:v[0] if len(v) == 1 else v for k, v in dd.items()}}
    if t.attrib:
        d[t.tag].update(('@' + k, v) for k, v in t.attrib.items())
    if t.text:
        text = t.text.strip()
        if children or t.attrib:
            if text:
              d[t.tag]['#text'] = text
        else:
            d[t.tag] = text
    return d

# hashes url + params
def make_cache_key(url, headers):
    header_str = json.dumps(headers, sort_keys=True, separators=(",", ":"))
    final = f"{url}|{header_str}"
    return hashlib.shake_256(final.encode()).hexdigest(4)

# hashes url + params
async def make_cache_keyASYNC(url, header_str):
    final = url + header_str
    return hashlib.shake_256(final.encode()).hexdigest(4)
    

## connects to an API with given headers, retrying transient failures (timeouts,
## connection errors, 5xx) with exponential backoff. 4xx errors (404, bad request,
## etc.) are treated as permanent and are not retried. Returns None if every
## attempt fails.
def connect(fullpath, headers, max_retries=3):
    delay = 0.5
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(fullpath, headers, timeout=20)
            response.raise_for_status()
        except HTTPError as http_err:
            retryable = getattr(http_err.response, 'status_code', 0) >= 500
            print(f'HTTP ERROR : {http_err}')
        except requests.exceptions.RequestException as err:
            retryable = True
            print(f'CONNECTION/TIMEOUT ERROR : {err}')
        except Exception as err:
            retryable = False
            print(f'MISC ERROR : {err}')
        else:
            return response
        if not retryable or attempt == max_retries:
            return None
        time.sleep(delay)
        delay *= 2

## connects to an API with given headers(in string format) asynchronously
## must specify if response is to be jsonified or not
## retries transient failures (timeouts, connection errors, 5xx) with exponential
## backoff; 4xx errors and JSON decode errors are treated as permanent
async def connectASYNC(session, fullpath, header_str, jsonify = True, timeout = 12, max_retries = 3):
    delay = 0.5
    for attempt in range(max_retries + 1):
        try:
            async with session.get(fullpath + header_str, timeout=timeout) as response:
                response.raise_for_status()
                if jsonify:
                    return await response.json()
                else:
                    return await response.text()
        except aiohttp.ClientResponseError as http_err:
            retryable = http_err.status >= 500
            print(f'HTTP ERROR {http_err.status} : {http_err} when connecting to {fullpath}')
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            retryable = True
            print(f'HTTP/TIMEOUT ERROR : {err} when connecting to {fullpath}')
        except json.JSONDecodeError as e:
            retryable = False
            print("Invalid JSON syntax:", e)
        except Exception as err:
            retryable = False
            print(f'MISC ERROR : {err} when connecting to {fullpath}')
        if not retryable or attempt == max_retries:
            break
        await asyncio.sleep(delay)
        delay *= 2
    # Callers (e.g. billHtml) treat '' as "no data" and degrade gracefully, so
    # return the sentinel instead of None on any failure.
    return ''

## raises a clear error instead of the opaque AttributeError that '.json()' on a
## failed (None) connect() response would otherwise produce
def _json_or_error(response, fullpath):
    if response is None:
        raise RuntimeError(f'Congress API request failed after retries: {fullpath}')
    return response.json()

## Caches external API requests, returns a json object (or None if the request failed)
def connect_and_cache(fullpath, headers, timeout = timeout_day):
    key = make_cache_key(fullpath, headers)
    cached = cache.get(key)
    if cached:
        return cached
    res = connect(fullpath, headers)
    if res is None:
        return None
    data = res.json()
    cache.set(key, data, timeout)
    return data

## ASYNC : Caches external API requests, returns a json object
## v2: bumped to abandon production entries poisoned with summary text/action lists
API_CACHE_VER = 'v2:'
async def connect_and_cacheASYNC(session, fullpath, header_str, timeout = 60*60*12):
    key = API_CACHE_VER + await make_cache_keyASYNC(fullpath, header_str)
    cached = await cache.aget(key)
    if cached:
        return cached

    # Single-flight / thundering-herd guard: when a hot key goes cold, many
    # concurrent requests would otherwise all stampede the upstream API at once
    # (each one blocking a worker thread). Instead, the first caller acquires a
    # short-lived lock and does the fetch; everyone else briefly polls the cache
    # for that result and only fetches themselves if the leader is slow/dies.
    # The lock is best-effort: any failure acquiring/releasing it falls back to the
    # prior behavior (fetch directly), so herd protection can never make a request
    # fail where it previously would have succeeded.
    lock_key = 'lock:' + key
    try:
        got_lock = await cache.aadd(lock_key, 1, timeout=20)
    except Exception:
        got_lock = True   # treat as "no waiting"; just fetch (no lock to release)
    if not got_lock:
        for _ in range(28):            # ~14s, just past the per-request fetch cap
            await asyncio.sleep(0.5)
            cached = await cache.aget(key)
            if cached:
                return cached
        # Leader never populated the cache (slow/failed) -> fetch it ourselves.

    try:
        data = await connectASYNC(session, fullpath, header_str)
        # Only cache real responses. Failures return '' (falsy); caching them is
        # pointless since the `if cached` guard above always re-fetches falsy
        # values -- this keeps the served-from-cache behavior exactly as before
        # while avoiding writing junk into Redis.
        if data:
            await cache.aset(key, data, timeout)
        return data
    finally:
        # Only the leader releases the lock; a waiter that fell through must not
        # delete someone else's lock.
        if got_lock:
            try:
                await cache.adelete(lock_key)
            except Exception:
                pass

## returns a list of responses from a list of requests asynchronously
async def run_concurrent_connect(session, requests, header_str) : 
    tasks = []
    for request in requests: 
        ret = connectASYNC(session, request, header_str)
        tasks.append(ret)
    return await asyncio.gather(*tasks, return_exceptions=True)

## returns a list of responses from a list of requests asynchronously with caching
async def run_concurrent_connect_and_cache(session, requests, header_str, timeout = timeout_day) : 
    tasks = []
    for request in requests: 
        ret = connect_and_cacheASYNC(session, request, header_str, timeout)
        tasks.append(ret)
    return await asyncio.gather(*tasks, return_exceptions=True)

# function that adds new_subjects to a unique set of subjects stored on redis cache
async def add_subjects(new_subjects):
    subjects = await cache.aget("bill_subjects", set())
    new_ids = await sync_to_async(list)(new_subjects.values_list("id", flat=True))
    subjects.update(new_ids)
    await cache.aset("bill_subjects", subjects, timeout=None)

## mega function to add members for a given congress
## to fully load a member we need to make an updateMember call adding image and other info
def addMembersCongressAPILazy(congress_num):
    headers = {
        'api_key' : settings.CONGRESS_KEY,
        'format' : 'json',
        'currentMember' : 'false',
        'offset' : '0', 'limit' : '250'
        }
    cong_url = settings.CONGRESS_DIR + '/congress/' + str(congress_num)
    API_cong = _json_or_error(connect(cong_url, headers), cong_url)
    start_date = API_cong['congress']['sessions'][0]['startDate']
    end_date = None if len(API_cong['congress']['sessions']) <= 2 else API_cong['congress']['sessions'][2]['endDate']
    members_url = settings.CONGRESS_DIR + "/member/congress/" + str(congress_num)
    API_response = _json_or_error(connect(members_url, headers), members_url)
    congress = Congress.objects.get_or_create(
        congress_num = congress_num,
        start_year = int(API_cong['congress']['startYear']),
        end_year = int(API_cong['congress']['endYear'])
        )[0]
    
    while (API_response != None):
        for member in API_response['members']:
            bioguide_id=member['bioguideId']
            in_house = member['district'] != None
            district = None if not in_house else member['district']
            member_set = Member.objects.filter(id = bioguide_id)
            if member_set.exists() and Membership.objects.filter(congress = congress, member = member_set[0], house = in_house).exists():
                continue    
            name = getFirstAndLastName(member['name'])
            full_name = name[0] + " "  + name[1]
            if (member_set.exists()):
                _member = member_set[0]
            else :
                _member = Member.objects.get_or_create(
                    id = bioguide_id, 
                    full_name = full_name,
                    first_name = name[0],
                    last_name = name[1],
                    image_link = "empty"
                    )[0]  
            state_code = reverse_state_dict[member['state']]
            Membership.objects.get_or_create(
                        congress = congress,
                        member = _member,
                        district_num = district,
                        house = in_house,
                        state = state_code,
                        geoid = state_fips[state_code] + ('' if not in_house else intToFIPS(district)),
                        party = member['partyName'],
                        start_date = start_date,
                        end_date = end_date,
                        )
            print("added member " + bioguide_id)
        if 'next' in API_response['pagination']:
            next_url = API_response['pagination']['next']
            API_response = _json_or_error(connect(next_url, {'api_key' : settings.CONGRESS_KEY}), next_url)
        else : API_response = None

## swap membership given bioguide_ids and dates of arrival and departure
## if departing member has no succesor, arriving_id should be "!"
def swapMembership(congress_num, leaving_id, in_house, leaving_date, arriving_id, arriving_date, party) :
    headers = {
        'api_key' : settings.CONGRESS_KEY,
        'format' : 'json',
        'currentMember' : 'false',
        'offset' : '0', 'limit' : '250'
        }
    in_house = (in_house == 1)
    congress = Congress.objects.get(congress_num__exact = congress_num)
    leaving_member = Member.objects.get(id = leaving_id)
    leaving_membership = Membership.objects.get(congress = congress, member = leaving_member, house = in_house)       
    if (arriving_id != "!") :
        _set_member = Member.objects.filter(id = arriving_id)
        if (_set_member.exists()):
            arriving_member = _set_member[0]
        else :
            member_url = settings.CONGRESS_DIR + 'member/' + arriving_id
            API_response_member = _json_or_error(connect(member_url, headers), member_url)
            arriving_member = Member.objects.get_or_create(
                id = arriving_id, 
                full_name = API_response_member['member']['directOrderName'],
                first_name = API_response_member['member']['firstName'],
                last_name = API_response_member['member']['lastName'],
                image_link = "empty"
                )[0]
        arriving_membership = Membership.objects.get_or_create(
            congress = congress,
            member = arriving_member,
            district_num = leaving_membership.district_num,
            house = in_house,
            state = leaving_membership.state,
            geoid = leaving_membership.geoid,
            party = party ,
            )[0]
        arriving_membership.start_date = arriving_date
        arriving_membership.end_date = leaving_membership.end_date
        arriving_membership.save()
    leaving_membership.end_date = leaving_date
    leaving_membership.save()

# updates the arrival date of a membership
def updateArrival(congress_id, arriving_id, arriving_date, in_house) :
    in_house = (in_house == 1)
    congress = Congress.objects.get(congress_num__exact = congress_id)
    member = Member.objects.get(id = arriving_id)
    membership = Membership.objects.get(congress = congress, member = member, house = in_house)       
    membership.start_date = arriving_date
    membership.save()

## creates a new membership with all required parameters (beyond arrival date is optional)
## DANGEROUS: will create a new membership even if one already exists if there is a slight
## variation from extant membership (ex: mistyped party)
def createMembership(congress_id, member_id, state, in_house, party, arrival_date, departure_date, district_num) :
    in_house = (in_house == 1) 
    congress = Congress.objects.get(congress_num__exact = congress_id)
    try:
        member = Member.objects.get(id = member_id)
    except:
        try:
            headers = {
                'api_key' : settings.CONGRESS_KEY,
                'format' : 'json',
                'currentMember' : 'false',
                'offset' : '0', 'limit' : '250'
                }
            member_url = settings.CONGRESS_DIR + 'member/' + member_id
            API_response_member = _json_or_error(connect(member_url, headers), member_url)
            member = Member.objects.get_or_create(
                id = member_id,
                full_name = API_response_member['member']['directOrderName'],
                first_name = API_response_member['member']['firstName'],
                last_name = API_response_member['member']['lastName'],
                image_link = "empty"
                )[0]
        except Exception as e:
            print(f"BioguideID not present in API or Congress API request failed: {e}")
            return
    membership = Membership.objects.get_or_create(
            congress = congress,
            member = member,
            district_num = district_num,
            house = in_house,
            state = state,
            geoid = state_fips[state] + ('' if not in_house else intToFIPS(district_num)),
            party = party ,
            start_date = arrival_date,
            end_date = departure_date
            )[0]
    membership.start_date = arrival_date
    membership.end_date = departure_date
    membership.save()

## updates database, adding new bills or updating bills and votes with actionDate GTE date_str
async def updateRecentBills(congress_num, date_str, bill_type):
    key = await make_cache_keyASYNC('last_processed_action_date?', bill_type)
    # if no date_str provided, we take the last_processed_action_date?{bill_type} date and use it as our limit
    if date_str == "!":
        cached = await cache.aget(key)
        if cached:
            date_str = cached
        else:
            date_str = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')

    last_processed_action_date = datetime.strptime(date_str, '%Y-%m-%d') - timedelta(days=1)
    tracked_latest_date = datetime.strptime(date_str, '%Y-%m-%d')
    header_str = '&api_key=' + settings.CONGRESS_KEY + f'&format=json&limit=250&fromDateTime={date_str}T00:00:00Z'
    session = aiohttp.ClientSession()
    vote_session = aiohttp.ClientSession()
    async with asyncio.TaskGroup() as tg:
        congress = tg.create_task(Congress.objects.aget(congress_num__exact = congress_num))
        API_response = tg.create_task(connectASYNC(
            session,
            settings.CONGRESS_DIR + "bill/" + str(congress_num) + "/" + bill_type + "?",
            header_str
            ))
    congress = congress.result()
    API_response = API_response.result()
    end_operation = False
    # connectASYNC returns '' (falsy, not None) on failure, so this must check
    # truthiness rather than "is not None" -- otherwise a failed fetch would loop
    # forever trying to index into the empty-string sentinel.
    while API_response:
        for bill in API_response['bills']:
            if bill['latestAction'] and 'actionDate' in bill['latestAction']:
                latest_action_date = datetime.strptime(bill['latestAction']['actionDate'], '%Y-%m-%d')
                if latest_action_date >= last_processed_action_date:
                    await addBillASYNC(session, vote_session, congress_num, bill_type, bill, congress, header_str, False)
                    if latest_action_date > tracked_latest_date:
                        tracked_latest_date = latest_action_date
        if 'next' in API_response['pagination']:
            API_response = await connectASYNC(session, API_response['pagination']['next'], header_str)
        else:
            API_response = None
    await cache.aset(key, tracked_latest_date.strftime('%Y-%m-%d'), 60 * 60 * 24)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(session.close())
        tg.create_task(vote_session.close())

## mega function that creates bills, and creates any votes for a given bill
## too many api calls will lead to being blocked by congress api
async def addBills(congress_num = 116, _type='s', limit = 100, offset = 0):
    header_str_sp = '&api_key=' + settings.CONGRESS_KEY + '&format=json&limit=' + str(limit) + '&offset=' + str(offset)
    header_str = '&api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=250'
    session = aiohttp.ClientSession()
    vote_session = aiohttp.ClientSession()
    async with asyncio.TaskGroup() as tg:
        congress = tg.create_task(Congress.objects.aget(congress_num__exact = congress_num))
        API_response = tg.create_task(connectASYNC(
            session,
            settings.CONGRESS_DIR + "bill/" + str(congress_num) + "/" + _type + "?",
            header_str_sp
            ))
    congress = congress.result()
    API_response = API_response.result()
    if not API_response:
        print(f'addBills: failed to fetch bill list for congress {congress_num}/{_type} (offset {offset}), aborting')
        async with asyncio.TaskGroup() as tg:
            tg.create_task(session.close())
            tg.create_task(vote_session.close())
        return
    indx = 0
    limit = 5
    n = len(API_response['bills'])
    while (indx < n) : 
        end = min (indx + limit, n)
        sets = API_response['bills'][indx:end]
        async with asyncio.TaskGroup() as tg:
            for bill in sets:
                tg.create_task(addBillASYNC(session, vote_session, congress_num, _type, bill, congress, header_str))
        indx = end
    print('added up to ' + str(offset + indx))
    if 'next' in API_response['pagination']:
        print(', need to get to ' + str(API_response['pagination']['count']))
    async with asyncio.TaskGroup() as tg:
        tg.create_task(session.close())
        tg.create_task(vote_session.close())

async def _sync_bill_relations(session, bill, congress_num, _type, num):
    """Fetch and sync cosponsors, related bills, and subjects from the Congress API."""
    base_url = settings.CONGRESS_DIR + 'bill/' + str(congress_num) + '/' + _type + '/' + str(num)
    header_str = '?api_key=' + settings.CONGRESS_KEY + '&format=json&limit=250'

    async with asyncio.TaskGroup() as tg:
        cosp_task = tg.create_task(connectASYNC(session, base_url + '/cosponsors', header_str))
        rel_task  = tg.create_task(connectASYNC(session, base_url + '/relatedbills', header_str))
        subj_task = tg.create_task(connectASYNC(session, base_url + '/subjects', header_str))

    cosp_data = cosp_task.result()
    rel_data  = rel_task.result()
    subj_data = subj_task.result()

    if cosp_data:
        cosps = cosp_data.get('cosponsors', [])
        ids = [c['bioguideId'] for c in cosps if 'bioguideId' in c]
        if ids:
            all_memberships = await sync_to_async(list)(
                Membership.objects.filter(congress=int(congress_num), member__id__in=ids).select_related('member')
            )
            mem_map = {(str(m.member.id), bool(m.house)): m for m in all_memberships}
            cosponsors = Membership.objects.none()
            for c in cosps:
                mobj = mem_map.get((c.get('bioguideId'), 'district' in c))
                if mobj:
                    cosponsors |= Membership.objects.filter(id=mobj.id)
            await bill.cosponsors.aset(cosponsors)

    if rel_data:
        related_ids = []
        for b in rel_data.get('relatedBills', []):
            try:
                n = int(b['number'])
                t = types[b['type'].lower()]
                if n < 10000:
                    _id = int(b['congress']) * 100000 + t * 10000 + n
                else:
                    _id = int(b['congress']) * 1000000 + t * 100000 + n
                related_ids.append(_id)
            except (KeyError, ValueError):
                continue
        if related_ids:
            await bill.related_bills.aset(Bill.objects.filter(id__in=related_ids))

    if subj_data:
        subjects_data = subj_data.get('subjects', {})
        names = [s['name'] for s in subjects_data.get('legislativeSubjects', []) if 'name' in s]
        if names:
            existing_names = {s async for s in bill.subjects.values_list('name', flat=True)}
            new_names = [n for n in names if n not in existing_names]
            await bill.subjects.aset(Subject.objects.filter(name__in=names))
            cache_key = f"Bill:{bill.id}"
            if not await cache.aget(cache_key):
                if new_names:
                    await add_subjects(Subject.objects.filter(name__in=new_names).all())
                await cache.aset(cache_key, True, timeout_day)
        bill.policy_area = subjects_data.get('policyArea', {}).get('name', 'Not Specified Yet.')
        await bill.asave()

_TEXT_CODES = frozenset()

async def compute_status_code(origin_code, action_codes_desc, initial_status=0):
    return max(initial_status, 0)

def compute_history_flags(action_codes_desc):
    return False, False

_PASSAGE_QUESTION_PATTERN = re.compile(r'(?!)')
_PASS_RESULTS = set()
_FAIL_RESULTS = set()

async def _update_status_from_vote(bill, vote):
    return False



# This will be run once for existing bills, it goes through
# all actions and updates status code rather than cutting
# action codes to latest_action (date) stored in bill data
async def getAllActionCodes(session, header_str, actions):
    if not actions:
        return []
    ret = [None] * int(actions['pagination']['count'])
    indx = 0
    while actions:
        for a in actions['actions']:
            ac = a.get('actionCode')
            if ac:
                try:
                    ac_int = int(ac)
                except (ValueError, TypeError):
                    ac_int = None
                text = a.get('text') if ac_int in _TEXT_CODES else None
                ret[indx] = (ac, text)
                indx += 1
        if 'next' in actions['pagination']:
            actions = await connectASYNC(session, actions['pagination']['next'], header_str)
        else:
            actions = None
    return ret[0:indx]

async def updateBill(congress_num, _type, num) :
    url = settings.CONGRESS_DIR + 'bill/' + str(congress_num) + '/' + _type + '/' + str(num) + '/actions?'
    header_str = '&api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=250'
    session = aiohttp.ClientSession()
    vote_session = aiohttp.ClientSession()
    if (int(num) < 10000):
        _id = congress_num * 100000 + types[_type] * 10000 + int(num)
    else :
        _id = congress_num * 1000000 + types[_type] * 100000 + int(num)
    async with asyncio.TaskGroup() as tg:
        congress = tg.create_task(Congress.objects.aget(congress_num__exact = congress_num))
        bill= tg.create_task(Bill.objects.aget(id__exact = _id))
        API_response_actions = tg.create_task(connectASYNC(session, url, header_str))
    congress = congress.result()
    bill = bill.result()
    API_response_actions = API_response_actions.result()
    if not API_response_actions:
        # Congress API didn't return the actions list -- bail out instead of
        # silently recomputing status_code from an empty action list, which would
        # reset an in-progress bill back to "Introduced".
        print(f'updateBill: failed to fetch actions for {_type}{num} (congress {congress_num}); skipping')
        async with asyncio.TaskGroup() as tg:
            tg.create_task(session.close())
            tg.create_task(vote_session.close())
        return
    action_codes_seen = []
    actions_complete = True
    while API_response_actions:
        for a in API_response_actions['actions']:
            ac = a.get('actionCode')
            if ac:
                try:
                    ac_int = int(ac)
                except (ValueError, TypeError):
                    ac_int = None
                text = a.get('text') if ac_int in _TEXT_CODES else None
                action_codes_seen.append((ac, text))
            if 'recordedVotes' in a:
                in_house = 0 if (a['recordedVotes'][0]['chamber'] != 'House') else 1
                vote_id = congress_num * 10000000 + in_house * 1000000 + int(a['recordedVotes'][0]['sessionNumber']) * 100000 + int(a['recordedVotes'][0]['rollNumber'])
                set_vote = Vote.objects.filter(id = vote_id)
                try:
                    vote_xml = await connectASYNC(vote_session, a['recordedVotes'][0]['url'], '', False)
                    if not vote_xml:
                        print(f"Empty vote XML response for vote {vote_id}, skipping")
                        return
                    vote_xml = ET.XML(vote_xml)
                except (aiohttp.ClientConnectionError, ET.ParseError) as e:
                    print(f"Connection error: {e}")
                    return
                vote_dict = etree_to_dict(vote_xml)
                dt = _vote_datetime(vote_dict, in_house)
                vote_data = {
                    'id': vote_id,
                    'congress': congress,
                    'house': in_house == 1,
                    'bill' : bill,
                    'question': vote_dict['rollcall-vote']['vote-metadata']['vote-question'] if in_house == 1 else vote_dict['roll_call_vote']['question'],
                    'title': vote_dict['rollcall-vote']['vote-metadata']['vote-desc'] if in_house == 1 else vote_dict['roll_call_vote']['vote_title'],
                    'result': vote_dict['rollcall-vote']['vote-metadata']['vote-result'] if in_house == 1 else vote_dict['roll_call_vote']['vote_result']
                }
                if not (await set_vote.aexists()):
                    vote_data['dateTime'] = dt
                vote = await Vote.objects.aget_or_create(**vote_data)
                vote = vote[0]
                members = vote_dict['rollcall-vote']['vote-data']['recorded-vote'] if in_house == 1 else vote_dict['roll_call_vote']['members']['member']
                if in_house == 1:
                    yea_ids, nay_ids, pres_ids, novt_ids = [], [], [], []
                    for m in members:
                        v = m['vote']
                        if v in ('Yea', 'Aye', 'Guilty'):      yea_ids.append(m['legislator']['@name-id'])
                        elif v in ('Nay', 'No', 'Not Guilty'): nay_ids.append(m['legislator']['@name-id'])
                        elif v == 'Present':                   pres_ids.append(m['legislator']['@name-id'])
                        else:                                  novt_ids.append(m['legislator']['@name-id'])
                    base = {'congress': congress, 'house': True}
                    yeas = Membership.objects.filter(**base, member__id__in=yea_ids)
                    nays = Membership.objects.filter(**base, member__id__in=nay_ids)
                    pres = Membership.objects.filter(**base, member__id__in=pres_ids)
                    novt = Membership.objects.filter(**base, member__id__in=novt_ids)
                else:
                    yea_q = nay_q = pres_q = novt_q = Q()
                    for m in members:
                        q = Q(member__last_name__iexact=m['last_name'], state=m['state'])
                        v = m['vote_cast']
                        if v in ('Yea', 'Aye', 'Guilty'):      yea_q |= q
                        elif v in ('Nay', 'No', 'Not Guilty'): nay_q |= q
                        elif v == 'Present':                   pres_q |= q
                        else:                                  novt_q |= q
                    base = {'congress': congress, 'house': False}
                    yeas = Membership.objects.filter(**base).filter(yea_q)  if yea_q  else Membership.objects.none()
                    nays = Membership.objects.filter(**base).filter(nay_q)  if nay_q  else Membership.objects.none()
                    pres = Membership.objects.filter(**base).filter(pres_q) if pres_q else Membership.objects.none()
                    novt = Membership.objects.filter(**base).filter(novt_q) if novt_q else Membership.objects.none()
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(vote.yeas.aset(yeas))
                    tg.create_task(vote.nays.aset(nays))
                    tg.create_task(vote.pres.aset(pres))
                    tg.create_task(vote.novt.aset(novt))
        if 'next' in API_response_actions['pagination']:
            next_page = await connectASYNC(session, API_response_actions['pagination']['next'], header_str)
            if not next_page:
                # Pagination broke partway through -- action_codes_seen is now
                # incomplete, so don't let it overwrite the bill's real status.
                actions_complete = False
            API_response_actions = next_page
        else:
            API_response_actions = None
    if not actions_complete:
        print(f'updateBill: pagination failed partway for {_type}{num} (congress {congress_num}); not updating status_code')
        async with asyncio.TaskGroup() as tg:
            tg.create_task(session.close())
            tg.create_task(vote_session.close())
        return
    bill.status_code = await compute_status_code(bill.getOriginCode(), action_codes_seen)
    bill.veto_in_history, bill.conf_in_history = compute_history_flags(action_codes_seen)
    await bill.asave()
    await _sync_bill_relations(session, bill, congress_num, _type, num)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(session.close())
        tg.create_task(vote_session.close())

## Given already-fetched+parsed vote XML (vote_dict, from etree_to_dict), builds/updates
## the Vote row and its yeas/nays/pres/novt Membership sets. Returns (vote, created).
## Shared by addBillASYNC and the House/Senate fast-path pipelines (checkHouseVotes/checkSenateVotes).
async def _create_or_update_vote(vote_id, congress, in_house, bill, vote_dict, ignore_exists, vote_exists, set_vote):
    dt = _vote_datetime(vote_dict, in_house)
    vote_data = {
        'id': vote_id,
        'congress': congress,
        'house': in_house == 1,
        'question': vote_dict['rollcall-vote']['vote-metadata']['vote-question'] if in_house == 1 else vote_dict['roll_call_vote']['question'],
        'title': vote_dict['rollcall-vote']['vote-metadata']['vote-desc'] if in_house == 1 else vote_dict['roll_call_vote']['vote_title'],
        'result': vote_dict['rollcall-vote']['vote-metadata']['vote-result'] if in_house == 1 else vote_dict['roll_call_vote']['vote_result']
    }
    if not vote_exists:
        vote_data['dateTime'] = dt
        vote, created = await Vote.objects.aget_or_create(**vote_data)
    else:
        vote = await set_vote.afirst()
        created = False
    vote.dateTime = dt
    if created or not ignore_exists:
        vote.bill = bill
    await vote.asave()
    if created or not ignore_exists:
        members = vote_dict['rollcall-vote']['vote-data']['recorded-vote'] if in_house == 1 else vote_dict['roll_call_vote']['members']['member']
        if in_house == 1:
            yea_ids, nay_ids, pres_ids, novt_ids = [], [], [], []
            for m in members:
                v = m['vote']
                if v in ('Yea', 'Aye', 'Guilty'):      yea_ids.append(m['legislator']['@name-id'])
                elif v in ('Nay', 'No', 'Not Guilty'): nay_ids.append(m['legislator']['@name-id'])
                elif v == 'Present':                   pres_ids.append(m['legislator']['@name-id'])
                else:                                  novt_ids.append(m['legislator']['@name-id'])
            base = {'congress': congress, 'house': True}
            yeas = Membership.objects.filter(**base, member__id__in=yea_ids)
            nays = Membership.objects.filter(**base, member__id__in=nay_ids)
            pres = Membership.objects.filter(**base, member__id__in=pres_ids)
            novt = Membership.objects.filter(**base, member__id__in=novt_ids)
        else:
            yea_q = nay_q = pres_q = novt_q = Q()
            for m in members:
                q = Q(member__last_name__iexact=m['last_name'], state=m['state'])
                v = m['vote_cast']
                if v in ('Yea', 'Aye', 'Guilty'):      yea_q |= q
                elif v in ('Nay', 'No', 'Not Guilty'): nay_q |= q
                elif v == 'Present':                   pres_q |= q
                else:                                  novt_q |= q
            base = {'congress': congress, 'house': False}
            yeas = Membership.objects.filter(**base).filter(yea_q)  if yea_q  else Membership.objects.none()
            nays = Membership.objects.filter(**base).filter(nay_q)  if nay_q  else Membership.objects.none()
            pres = Membership.objects.filter(**base).filter(pres_q) if pres_q else Membership.objects.none()
            novt = Membership.objects.filter(**base).filter(novt_q) if novt_q else Membership.objects.none()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(vote.yeas.aset(yeas))
            tg.create_task(vote.nays.aset(nays))
            tg.create_task(vote.pres.aset(pres))
            tg.create_task(vote.novt.aset(novt))
    return vote, created

# meant to be used asynchronously to add batches of bills at one time
async def addBillASYNC(session, vote_session, congress_num, _type, b, congress, header_str, ignore_exists = True):
    if (int(b['number']) < 10000):
        _id = congress_num * 100000 + types[_type] * 10000 + int(b['number'])
    else :
        _id = congress_num * 1000000 + types[_type] * 100000 + int(b['number'])
        ignore_exists = False
    set_bill = Bill.objects.filter(id = _id)
    async with asyncio.TaskGroup() as tg:
        bill_exists = tg.create_task(set_bill.aexists())
        API_response_bill = tg.create_task(connectASYNC(session, b['url'], header_str))
    API_response_bill = API_response_bill.result()
    bill_exists = bill_exists.result()
    if (bill_exists and ignore_exists) or (API_response_bill['bill']['title'][:8] == 'Reserved') : return
    async with asyncio.TaskGroup() as tg:
        API_response_actions = tg.create_task(connectASYNC(session, API_response_bill['bill']['actions']['url'], header_str))
        member = tg.create_task(Member.objects.aget(id=API_response_bill['bill']['sponsors'][0]['bioguideId']))
    API_response_actions = API_response_actions.result()
    API_response_actions_store = API_response_actions
    member = member.result()
    date = API_response_bill['bill']['introducedDate'].split('-')
    dtime = datetime(int(date[0]), int(date[1]), int(date[2]))
    in_house = API_response_bill['bill']['sponsors'][0]['fullName'][0] == 'R'
    try:
        membership = await Membership.objects.aget(congress=congress, member=member, start_date__lte = dtime, house= in_house )
    except:
        print('Membership not Found')
        return
    enacted = ('laws' in API_response_bill['bill']) and (len(API_response_bill['bill']['laws']) > 0)
    status = enacted
    status_code = 61 if enacted else 0

    # Track previous latest_api_update when bill already exists so we can stop processing older actions.
    # latest_api_update is an internal-only watermark for this pipeline -- it is never touched by
    # the House/Senate fast-path pipelines, so it always reflects the literal official API value.
    prev_latest_action = None
    official_date_str = API_response_bill['bill']['latestAction']['actionDate']
    if (bill_exists) :
        bill = await Bill.objects.aget(id = _id)
        # preserve previous latest_api_update (DateField) for early exit while processing actions
        prev_latest_action = bill.latest_api_update
        bill.title = b['title']
        bill.status = status
        bill.latest_api_update = official_date_str
        # latest_action may already have been advanced ahead of the official API by a
        # fast-path (House/Senate) vote detection -- never regress it, only bump forward.
        # NOTE: use datetime.strptime(...).date() here, not date.fromisoformat() -- the
        # local variable `date` above (introducedDate split) shadows the datetime.date
        # class for the rest of this function.
        official_date = datetime.strptime(official_date_str, '%Y-%m-%d').date()
        if bill.latest_action is None or official_date > bill.latest_action:
            bill.latest_action = official_date
        await bill.asave()
    else :
        bill = await Bill.objects.aget_or_create(
            id = _id,
            title = b['title'],
            sponsor = membership,
            status = status,
            status_code = status_code,
            origin_date = API_response_bill['bill']['introducedDate'],
            latest_action = official_date_str,
            latest_api_update = official_date_str,
            )
        bill = bill[0]

    # Normalize prev_latest_action to a date object if present
    if prev_latest_action is not None and isinstance(prev_latest_action, datetime):
        prev_latest_action = prev_latest_action.date()
    new_action = False
    new_vote = False
    action_codes_seen = []
    actions_complete = True

    # connectASYNC returns '' (falsy, not None) on failure, so this must check
    # truthiness -- "is not None" would let a failed fetch fall through to
    # indexing into the empty-string sentinel below.
    while API_response_actions:
        for a in API_response_actions['actions']:
            # If the bill already existed and we reach an action older-or-equal to the stored previous latest_action,
            # stop processing further actions for this bill (and pagination).
            try:
                action_date = datetime.strptime(a['actionDate'], '%Y-%m-%d').date()
            except Exception:
                action_date = None
            if prev_latest_action is not None and action_date is not None and action_date < prev_latest_action:
                # stop processing further actions (they are older)
                API_response_actions = None
                break
            ac = a.get('actionCode')
            if ac:
                try:
                    ac_int = int(ac)
                except (ValueError, TypeError):
                    ac_int = None
                text = a.get('text') if ac_int in _TEXT_CODES else None
                action_codes_seen.append((ac, text))
            new_action = True
            if 'recordedVotes' in a:
                in_house = 0 if (a['recordedVotes'][0]['chamber'] != 'House') else 1
                vote_id = congress_num * 10000000 + in_house * 1000000 + int(a['recordedVotes'][0]['sessionNumber']) * 100000 + int(a['recordedVotes'][0]['rollNumber'])
                set_vote = Vote.objects.filter(id = vote_id)
                vote_exists = await set_vote.aexists()
                if ignore_exists and vote_exists:
                    continue
                try:
                    vote_xml = await connectASYNC(vote_session, a['recordedVotes'][0]['url'], '', False)
                    if not vote_xml:
                        print(f"Empty vote XML response for vote {vote_id}, skipping")
                        return
                    vote_xml = ET.XML(vote_xml)
                except (aiohttp.ClientConnectionError, ET.ParseError) as e:
                    print(f"Connection error: {e}")
                    return
                vote_dict = etree_to_dict(vote_xml)
                vote, created = await _create_or_update_vote(vote_id, congress, in_house, bill, vote_dict, ignore_exists, vote_exists, set_vote)
                if created:
                    new_vote = True
                    await send_bill_notification(
                        bill_id=bill.id,
                        title="New Vote",
                        body="A new vote was taken on Bill " + bill.__str__() + "."
                    )

        if API_response_actions is not None and 'next' in API_response_actions['pagination']:
            next_page = await connectASYNC(session, API_response_actions['pagination']['next'], header_str)
            if not next_page:
                # Pagination broke partway through -- action_codes_seen is now
                # incomplete, so don't let it understate the bill's real status.
                actions_complete = False
            API_response_actions = next_page
        else:
            API_response_actions = None
    origin_code = bill.getOriginCode()
    if not actions_complete:
        print(f'addBillASYNC: pagination failed partway for bill {_id}; skipping status update')
        await _sync_bill_relations(session, bill, congress_num, _type, b['number'])
        return 1
    if bill.status_code == -1:
        action_codes_seen = await getAllActionCodes(session, header_str, API_response_actions_store)
    new_sc = await compute_status_code(
        origin_code, action_codes_seen,
        initial_status=bill.status_code if bill_exists else 0,
    )
    if enacted:
        new_sc = max(new_sc, 61)
    new_veto, new_conf = compute_history_flags(action_codes_seen)
    new_veto = new_veto or bill.veto_in_history
    new_conf = new_conf or bill.conf_in_history
    if new_sc != bill.status_code or new_veto != bill.veto_in_history or new_conf != bill.conf_in_history:
        bill.status_code = new_sc
        bill.veto_in_history = new_veto
        bill.conf_in_history = new_conf
        await bill.asave()
    await _sync_bill_relations(session, bill, congress_num, _type, b['number'])
    if new_action:
        if _type in SENATE_TYPES:
            _senate_bill_ids_this_run.add(_id)
        else:
            _house_bill_ids_this_run.add(_id)
        if not new_vote:
            await send_bill_notification(
                bill_id=bill.id,
                title="New Action",
                body="New action(s) were taken on Bill " + bill.__str__() + "."
            )
    return 1

## Fast-path House/Senate vote pipelines -------------------------------------------------
## The official Congress API is often a day or more behind on posting floor-vote actions.
## The House Clerk and Senate.gov publish roll-call results within minutes. These two
## pipelines check those pages directly and bump Bill.latest_action forward when they find
## a bill-related vote not yet reflected in the DB, without ever touching latest_api_update
## (the official pipeline's own internal bookkeeping field, see addBillASYNC above).

# Maps the congress.gov bill-page URL slug (seen in House index-page hrefs) to the
# existing `types` dict keys.
_BILL_URL_SLUG_TO_TYPE = {
    'house-bill': 'hr', 'house-resolution': 'hres',
    'house-joint-resolution': 'hjres', 'house-concurrent-resolution': 'hconres',
    'senate-bill': 's', 'senate-resolution': 'sres',
    'senate-joint-resolution': 'sjres', 'senate-concurrent-resolution': 'sconres',
}
# Maps a normalized Senate <issue> tag prefix (dots/spaces stripped, uppercased) to
# the same `types` dict keys. Anything not in here (e.g. "PN" nominations) is skipped.
_SENATE_ISSUE_PREFIXES = {
    'S': 's', 'SRES': 'sres', 'SJRES': 'sjres', 'SCONRES': 'sconres',
    'HR': 'hr', 'HRES': 'hres', 'HJRES': 'hjres', 'HCONRES': 'hconres',
}
_MAX_HOUSE_ROLL_BLOCKS_PER_RUN = 3

def _make_bill_id(congress_num, _type, number):
    # mirrors the encoding already used in addBillASYNC
    if number < 10000:
        return congress_num * 100000 + types[_type] * 10000 + number
    return congress_num * 1000000 + types[_type] * 100000 + number

def _session_for_year(year):
    # matches the existing precedent in fixHouseVote (session 1 = odd calendar year)
    return 1 if (year % 2 == 1) else 2

def _parse_day_mon_date(date_text, year):
    # "23-Jul" + 2026 -> "2026-07-23"
    day, mon = date_text.strip().split('-')
    return f"{year}-{month_to_num[mon]}-{day.zfill(2)}"

async def _vote_watermark(congress_num, house, session):
    return None, 0

def _parse_house_vote_rows(html, year):
    return []

async def _fetch_house_roll_range_pages(session_http, year, lo, hi, max_blocks):
    return []

async def checkHouseVotes(congress_num=None, year=None):
    return None

def _parse_senate_issue(issue_text):
    return None, None

async def checkSenateVotes(congress_num=None, session=None):
    return None

async def merge_fastpath_votes(bill, actions):
    return actions

# runs through existing votes up to limit, and adds memberships that were missing
async def fixHouseVotes(congress_num, year, nums, member_ids) :
    session = aiohttp.ClientSession()
    congress = await Congress.objects.aget(congress_num__exact = congress_num)
    indx = 1
    limit = 5
    while (indx <= nums) : 
        end = min (indx + limit, nums + 1)
        async with asyncio.TaskGroup() as tg:
            for i in range(indx, end):
                tg.create_task(fixHouseVote(session, congress, congress_num, year, i, member_ids))
        indx = end
    print('Fixed ' + str(nums) + ' votes. Check your vote table to see if everything is correct.')
    await session.close()

async def fixHouseVote(session, congress, congress_num, year, num, member_ids) :
    # CCC_H_S_XXXXX
    sess = 1 if (year % 2 == 1) else 2
    vote_id = congress_num * 10000000 + 1000000 + sess * 100000 + num
    url = "http://clerk.house.gov/cgi-bin/vote.asp?year=" + str(year) + "&rollnumber=" + str(num)
    set_vote = Vote.objects.filter(id = vote_id)
    if await set_vote.aexists():
        vote = await Vote.objects.aget(id = vote_id)
        try:
            vote_xml = await connectASYNC(session, url, '', False)
            if not vote_xml:
                print(f"Empty vote XML response for vote {vote_id}, skipping")
                return
            vote_xml = ET.XML(vote_xml)
        except (aiohttp.ClientConnectionError, ET.ParseError) as e:
            print(f"Connection error: {e}")
            return
        vote_dict = etree_to_dict(vote_xml)
        member_votes = {
                        'Yea': vote.yeas,
                        'Aye': vote.yeas,
                        'Guilty': vote.yeas,
                        'Nay': vote.nays,
                        'No': vote.nays,
                        'Not Guilty': vote.nays,
                        'Not Voting': vote.novt,
                        'Present': vote.pres
                    }
        members = vote_dict['rollcall-vote']['vote-data']['recorded-vote']
        for m in members :
            if m['legislator']['@name-id'] in member_ids :
                _set = member_votes[m['vote']].filter(congress=congress, member__id=m['legislator']['@name-id'], house = True)
                if not await _set.aexists() :
                    member = await Membership.objects.aget(congress=congress, member__id=m['legislator']['@name-id'], house = True)
                    await member_votes[m['vote']].aadd(member)


def getFirstAndLastName(reverseName):
    try:
        commaIndx = reverseName.index(',')
    except ValueError:
            return ValueError
    lastName = reverseName[:commaIndx]
    commaIndx += 1
    while (reverseName[commaIndx] == ' '):
        commaIndx+=1
    endIndx = commaIndx
    while(endIndx != len(reverseName)):
        if (reverseName[endIndx] in {' ', ','}):
            break
        endIndx+=1
    return [reverseName[commaIndx: endIndx], lastName]

def getNumSuffix(num):
    num = num % 100
    if (num % 10 == 1 and num // 10 != 1) : return 'st'
    elif (num % 10 == 2 and num // 10 != 1) : return 'nd'
    elif (num % 10 == 3 and num // 10 != 1) : return 'rd'
    return 'th'

def _vote_datetime(vote_dict, in_house):
    """Aware UTC datetime for a roll-call vote payload.

    Both chambers publish Washington (Eastern) wall-clock times: the House clerk
    XML as action-date '23-Jul-2026' + action-time/@time-etz '14:15', the Senate
    LIS XML as vote_date 'July 23, 2026,  02:15 PM'. They used to be stored with
    a 'Z' suffix, i.e. 4-5 hours off; zoneinfo applies the right DST offset.
    """
    if in_house:
        meta = vote_dict['rollcall-vote']['vote-metadata']
        day, mon, year = meta['action-date'].split('-')
        hour, minute = meta['action-time']['@time-etz'].split(':')
        local = datetime(int(year), int(month_to_num[mon[:3]]), int(day), int(hour), int(minute))
    else:
        month_day, year, clock = [p.strip() for p in vote_dict['roll_call_vote']['vote_date'].split(',')]
        month_name, day = month_day.split()
        local = datetime.strptime(
            f"{year}-{month_to_num[month_name[:3]]}-{int(day):02d} {' '.join(clock.split())}",
            '%Y-%m-%d %I:%M %p')
    return local.replace(tzinfo=US_EASTERN).astimezone(dt_timezone.utc)

def findIndexOfRoleByChamberAndCongress(roles, congress_num, chamber):
    for i in range(len(roles)):
        if (roles[i]['congress'] == str(congress_num)) & (roles[i]['chamber'] == chamber): 
            return i
    return -1    
                    
## returns the member's API payload (dict), or None if the Congress API request failed
def updateMember(congress_num, member_id):
    congress = Congress.objects.get(congress_num__exact = congress_num)
    member = Member.objects.get(id__exact = member_id)
    API_response_member = connect_and_cache(member.getAPIURL(), {'api_key' : settings.CONGRESS_KEY, 'format' : 'json'}, timeout_day * 7)
    if API_response_member is None:
        return None
    image_link = member.image_link
    if image_link != "empty" and member.official_link != None and member.office != None and member.phone != None: return API_response_member
    
    office_addr = None
    phone_num = None
    death_year = None
    site = None
    
    if ('deathYear' in API_response_member['member']) :
        death_year = API_response_member['member']['deathYear']
        
    if (API_response_member['member']['currentMember']) :
        site = API_response_member['member'].get('officialWebsiteUrl', None)
        if 'officeAddress' in API_response_member['member'].get('addressInformation', {}):
            office_addr = API_response_member['member']['addressInformation']['officeAddress']
            
        if 'phoneNumber' in API_response_member['member']['addressInformation']:
            phone_num = API_response_member['member']['addressInformation']['phoneNumber']

    ## find this term's party
    if (len(API_response_member['member']['partyHistory']) > 1):
        _membership = Membership.objects.get(congress = congress, member = member)
        for hist in API_response_member['member']['partyHistory']:
            if (hist['startYear'] < congress.end_year and ('endYear' not in hist or hist['endYear'] > congress.start_year)):
                _membership.party = hist['partyName']
                _membership.save()
                break
    if ('depiction' in API_response_member['member']) :
        image_link = API_response_member['member']['depiction']['imageUrl']

    Member.objects.filter(id = member_id).update(
        full_name = API_response_member['member']['directOrderName'],
        first_name = API_response_member['member']['firstName'],
        last_name = API_response_member['member']['lastName'], 
        image_link = image_link,
        office = office_addr,
        official_link = site,
        birth_year = API_response_member['member']['birthYear'],
        death_year = death_year,
        phone = phone_num
        )
    # need to somehow store history of legislation and party history and leadership
    return API_response_member

# takes s_d (start date) and e_d (end date) strings with fomat YYYY-MM-DD and bill type (string abstraction)
# returns bills (queryset) of bill type in date range
def getBillsInRange(s_d, e_d, bill_type, topics):
    start = s_d.split('-')
    end = e_d.split('-')
    start_date = datetime(int(start[0]), int(start[1]), int(start[2]))
    end_date = datetime(int(end[0]), int(end[1]), int(end[2]))
    if bill_type != '!':
        qs = Bill.type_objects.get_from_type(bill_type, start_date, end_date)
    else :
        qs = Bill.objects.filter(latest_action__gte=start_date, latest_action__lte=end_date)
    if len(topics) > 0:
        qs = qs.annotate(
                match_count=Count(
                    "subjects",
                    filter=Q(subjects__in=topics),
                    distinct=True
                )
            ).filter(match_count__gt=0)
        qs = qs.order_by("-match_count", "-latest_action", "-id")

    return qs


# takes s_d (start date) and e_d (end date) strings with fomat YYYY-MM-DD and bill type (string abstraction)
# returns votes (queryset) of bill type in date range
def getVotesInRange(s_d, e_d, bill_type, topics):
    start = s_d.split('-')
    end = e_d.split('-')
    # Whole days in Washington time, matching the dates shown on vote pages.
    start_date = datetime(int(start[0]), int(start[1]), int(start[2]), 0, 0, 0, tzinfo=US_EASTERN)
    end_date = datetime(int(end[0]), int(end[1]), int(end[2]), 23, 59, 59, tzinfo=US_EASTERN)
    if bill_type != '!':
        qs = Vote.type_objects.get_from_type(bill_type, start_date, end_date)
    else :
       qs = Vote.objects.filter(dateTime__gte=start_date, dateTime__lte=end_date)
    if len(topics) > 0:
        qs = qs.annotate(
                match_count=Count(
                "bill__subjects",
                filter=Q(bill__subjects__in=topics),
                distinct=True
            )
        ).filter(match_count__gt=0)

        qs = qs.order_by("-match_count", "-dateTime", "-id")
    return qs

def intToFIPS(num):
    if num < 10 : return '0' + str(num)
    return str(num)

##  return a context for http request to fill html page with content
async def billHtml(bill, congress_id, bill_type, num):
    """Own the aiohttp session lifecycle so it is ALWAYS closed -- even if the
    body raises (BillUpstreamUnavailable, a DB error, a parse error, etc.).
    Previously the session was only closed on the success path, leaking
    connections on every failure. The bounded ClientTimeout is a backstop in case
    a call ever reaches session.get without an explicit per-request timeout."""
    session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15, connect=5))
    try:
        return await _billHtml_impl(session, bill, congress_id, bill_type, num)
    finally:
        await session.close()


async def _billHtml_impl(session, bill, congress_id, bill_type, num):
    apiURL = settings.CONGRESS_DIR + "bill/" + congress_id + "/" + bill_type + "/" + num
    header_str = '?api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=250'
    requests = [apiURL, apiURL + '/actions', apiURL + '/summaries']
    API_data = await run_concurrent_connect_and_cache(session, requests, header_str)
    # If the core bill payload didn't come back (upstream slow/down -> connectASYNC
    # returned '', or gather captured an exception), bail out cleanly instead of
    # crashing on a non-dict subscript. Raising here lets the view render a friendly
    # "temporarily unavailable" page rather than a 500 that coincides with the
    # worker being killed. The session is closed by the billHtml wrapper.
    if not (isinstance(API_data[0], dict) and 'bill' in API_data[0]
            and isinstance(API_data[1], dict) and 'actions' in API_data[1]):
        raise BillUpstreamUnavailable(
            f'Congress API did not return core data for {congress_id}/{bill_type}/{num}'
        )
    date_str = API_data[0]['bill']['updateDate']
    update_date = date(
        int(date_str[0:4]),
        int(date_str[5:7]),
        int(date_str[8:10])
        )
    current_date = date.today()
    valid_update = (bill.latest_db_update == None) or (int(congress_id) == current_congress and update_date > bill.latest_db_update)
    if valid_update:
        requests = [apiURL + '/cosponsors', apiURL + '/relatedbills', apiURL + '/subjects']
        API_data_2 = await run_concurrent_connect_and_cache(session, requests, header_str)

        # Optimize cosponsors: fetch memberships in batch instead of per-cosponsor DB query
        if (API_data_2[0] != ''):
            cosponsors_exist = True
            cosps = API_data_2[0].get('cosponsors', [])
            # Build list of member ids and a map of (bioguideId, house_bool) -> list index
            ids = [c['bioguideId'] for c in cosps if 'bioguideId' in c]
            if ids:
                # fetch all memberships for those members in one query
                all_memberships = Membership.objects.filter(congress=int(congress_id), member__id__in=ids).select_related('member')
                # map by (member_id, house_bool) for quick lookup
                mem_map = {}
                for m in await sync_to_async(list)(all_memberships):
                    mem_map[(str(m.member.id), bool(m.house))] = m
                cosponsors = Membership.objects.none()
                for c in cosps:
                    mid = c.get('bioguideId')
                    house_flag = ('district' in c)
                    key = (mid, house_flag)
                    mobj = mem_map.get(key)
                    if mobj:
                        cosponsors |= Membership.objects.filter(id=mobj.id)
                await bill.cosponsors.aset(cosponsors)
        
        # Optimize related bills: collect ids then single query
        if (API_data_2[1] != ''):
            related_exist = True
            related_list = API_data_2[1].get('relatedBills', [])
            related_ids = []
            for b in related_list:
                # Wide (>9999) numbers use the CCC_T_XXXXX layout; see models.Bill.
                related_ids.append(_make_bill_id(int(b['congress']), b['type'].lower(), int(b['number'])))
            if related_ids:
                related_bills = Bill.objects.filter(id__in=related_ids)
                await bill.related_bills.aset(related_bills)

        # Optimize subjects: fetch with one query using name__in
        if (API_data_2[2] != ''):
            subjects_exist = True
            subj_list = API_data_2[2].get('subjects', {}).get('legislativeSubjects', [])
            names = [s['name'] for s in subj_list if 'name' in s]
            if names:
                subjects = Subject.objects.filter(name__in=names)
                await bill.subjects.aset(subjects)
            bill.policy_area = ('Not Specified Yet.' if not ('policyArea' in API_data_2[2]['subjects']) else API_data_2[2]['subjects']['policyArea']['name'])
            await bill.asave()

        bill.latest_db_update = current_date
        await bill.asave()
    context = {'title':"CONGRESS: " + congress_id + ", " + bill_type.upper() + "-" + num,
            'bill' : bill_type.upper() + "-" + num,
            }
    if (API_data[1]['actions']) and ('actionCode' in API_data[1]['actions'][0]) and (API_data[1]['actions'][0]['actionCode'] in ['E40000', '36000']) :
        context['bill_state_type'] = 'Became Public Law'
    else :
        context['bill_state_type'] = 'Still Just a Bill'

    # Bill status pipeline
    sc = getattr(bill, 'status_code', None)
    if sc is None:
        sc = 61 if bill.status else 0
    context['pipeline_data'] = {
        'status_code': sc,
        'origin': bill.getOrigin(),
        'outer': 'House' if bill.getOrigin() == 'Senate' else 'Senate',
        'conf_in_history': bool(getattr(bill, 'conf_in_history', False)),
        'veto_in_history': bool(getattr(bill, 'veto_in_history', False)),
        'passed': bool(bill.status),
    }

    API_data[1]['actions'] = await merge_fastpath_votes(bill, API_data[1]['actions'])
    context['actions_table'] = await actionTable(API_data[1], bill_type, num)
    member_link = '/member/results/?congress='
    bill_link = '/bill/'
    q_2 = '&member='
    q_3 = '&chamber='

    _party_class = {
        'Democratic': 'member-party-tag--d',
        'Republican': 'member-party-tag--r',
        'Independent': 'member-party-tag--i',
    }

    async def memberURL(mem):
        chamber = 'House+of+Representatives' if mem.house else 'Senate'
        member_full = await sync_to_async(getattr)(mem, 'member', None)
        if member_full:
            name = member_full.full_name
        else:
            name = (await Member.objects.aget(id=mem.member_id)).full_name
        location = mem.state + ('' if not mem.house else '-' + str(mem.district_num))
        label = name + ' · ' + mem.party[0] + ' · ' + location
        party_cls = _party_class.get(mem.party, 'member-party-tag--other')
        return '<a class="member-party-tag ' + party_cls + '" href="' + member_link + congress_id + q_2 + mem.member_id + q_3 + chamber + '">' + label + '</a>'
    context['sponsor'] = await memberURL(await Membership.objects.aget(id=bill.sponsor_id))
    cosponsors_exist, related_exist, subjects_exist = await asyncio.gather(
        bill.cosponsors.aexists(),
        bill.related_bills.aexists(),
        bill.subjects.aexists()
        )
    if (cosponsors_exist):
        co_list = ''
        async for c in bill.cosponsors.all().select_related('member'):
            co_list += await memberURL(c)
        context['cosponsors'] = co_list
        
    if (related_exist):
        related_bills = ''
        async for b in bill.related_bills.all():
            related_bills += '<a class="subject-tag subject-tag--link" href="' + bill_link + b.getURL() + '">' + str(b) + '</a>'
        context['related_bills'] = related_bills
                  
    if (subjects_exist):
        sub_list = ''
        async for s in bill.subjects.filter(subtype=0).all():
            sub_list += '<span class="subject-tag subject-tag--muted">' + s.name + '</span>'
        context['subjects'] = sub_list
        sub_list_1 = ''
        async for s in bill.subjects.filter(subtype=1).all():
            sub_list_1 += '<span class="subject-tag subject-tag--muted">' + s.name + '</span>'
        context['subjects_1'] = sub_list_1
        sub_list_2 = ''
        async for s in bill.subjects.filter(subtype=2).all():
            sub_list_2 += '<span class="subject-tag subject-tag--muted">' + s.name + '</span>'
        context['subjects_2'] = sub_list_2
        context['policy_area'] = bill.policy_area
      
    # currently just gets first summary in list...
    if (API_data[2] != ''):
        if (int(num) < 10000):
            _id = int(congress_id) * 100000 + types[bill_type] * 10000 + int(num)
        else :
            _id = int(congress_id) * 1000000 + types[bill_type] * 100000 + int(num)

    # Prefer Congress-provided summary. If none, fall back to DB-stored BillSummary.
    # Only show a "Generate AI summary" button when there's neither a Congress summary nor a stored BillSummary.
    api_summaries = None
    if (API_data[2] != ''):
        api_summaries = API_data[2].get('summaries', [])

    if api_summaries and len(api_summaries) > 0:
        # Use official Congress API summary and remove any stored/generated summary
        context['AI_generated_content'] = "CONGRESS"
        context['summary'] = api_summaries[0]['text']
        await BillSummary.objects.filter(id=_id).adelete()
    else:
        # No Congress summary: check for an existing stored BillSummary
        try:
            bill_summary = await BillSummary.objects.aget(id=_id)
            # If DB summary exists and is non-empty, use it; otherwise treat as absent
            if bill_summary.summary and bill_summary.summary.strip() and bill_summary.summary != "We cannot provide a summary at this time.":
                context['AI_generated_content'] = "STORED"
                context['summary'] = bill_summary.summary
                context['ai_generated_date'] = bill_summary.generated_at
            else:
                # DB record exists but no usable summary -> allow user to generate
                context['AI_generated_content'] = "NONE"
                context['summary'] = ""
                context['show_generate_button'] = True
        except BillSummary.DoesNotExist:
            # No DB summary -> do not auto-generate; show button to let user request AI generation
            context['AI_generated_content'] = "NONE"
            context['summary'] = ""
            context['show_generate_button'] = True

    # session is closed by the billHtml wrapper's finally block.
    return context

SUMMARY_TOO_LARGE = "__BILL_TOO_LARGE__"
SUMMARY_OVERLOADED = "__OVERLOADED__"

async def getSummaryAI(session, url, header_str, _id):
    return ''

def voteHtml(vote):
    congress_id = str(vote.congress.congress_num)
    q_2 = '&member='
    q_3 = '&chamber='
       
    # Load related Membership rows (and their Member) in as few queries as possible.
    # Evaluate each queryset into a list once to avoid repeated DB hits during iteration.
    nays_qs = vote.nays.all().select_related('member')
    yeas_qs = vote.yeas.all().select_related('member')
    pres_qs = vote.pres.all().select_related('member')
    novt_qs = vote.novt.all().select_related('member')

    votes_iters = [list(nays_qs), list(yeas_qs), list(pres_qs), list(novt_qs)]

    list_color = {
        'Democratic': 'dem',
        'Republican': 'rep',
        'Independent': 'ind',
        'Libertarian': 'lib',
        'Green': ' grn'
    }

    # Prepare mutable accumulators
    html_rows = [[] for _ in range(4)]          # collect rows per vote-category, join at end
    partyCountsbyVote = [defaultdict(int) for _ in range(4)]
    isHouseVote = vote.house

    if isHouseVote:
        mult = 435
        values = [0] * mult
        text = [''] * mult
    else:
        mult = 50
        values = [[0] * mult for _ in range(4)]
        text = state_list

    geoids = [None] * mult

    # We need to preserve the original iteration order: [nays, yeas, pres, novt]
    j = 0  # running index used for House mapping (keeps order across categories)
    for i in range(4):
        for membership in votes_iters[i]:
            party = membership.party
            partyCountsbyVote[i][party] += 1

            # Skip malformed geoids
            geoid = membership.geoid
            if not geoid:
                continue

            if isHouseVote:
                # geoid like '06XX' -> prefix '06'
                prefix = geoid[:2]
                idx = fips_to_count.get(prefix)
                # fallback if mapping missing
                if idx is None:
                    # still populate a sequential list-based view
                    try:
                        text[j] = state_list[fips_to_count[geoid[:2]]] + '-' + geoid[2:]
                    except Exception:
                        text[j] = '-' + geoid[2:]
                    geoids[j] = geoid
                    values[j] = i
                    j += 1
                else:
                    text[j] = state_list[idx] + '-' + geoid[2:]
                    geoids[j] = geoid
                    values[j] = i
                    j += 1
                chamber = 'House+of+Representatives'
            else:
                # For Senate, membership.geoid is the state FIPS code
                indx = fips_to_count.get(geoid)
                if indx is None:
                    # skip territories not in mapping
                    continue
                geoids[indx] = geoid
                values[i][indx] += 1
                chamber = 'Senate'

            # Build html row using pre-resolved attributes (select_related('member') loaded Member)
            # Use getStr() because it likely formats membership display consistently.
            css = list_color.get(party, '')
            member_id = membership.member.id
            # Avoid multiple concatenations per loop � append to list and join later.
            img_link = membership.member.image_link or ''
            row = (
                f'<tr class="{css} border">'
                f'<td class="border-0"><a href="/member/results/?congress='
                f'{congress_id}{q_2}{member_id}{q_3}{chamber}" class="link-light"'
                f' data-img="{img_link}">'
                f'{membership.getStr()}</a></td></tr>'
            )
            html_rows[i].append(row)

    # finalize html strings
    html_lists = [''.join(html_rows[i]) for i in range(4)]

    # compute counts from the already-evaluated lists to avoid extra DB queries
    counts = [len(votes_iters[i]) for i in range(4)]

    context = {
        'title': str(vote.id),
        'bill' : vote.bill.__str__(),
        'bill_title' : vote.bill.title,
        'bill_link' : '/bill/' + congress_id  + '/' + vote.bill.getTypeURL() + '/' + vote.bill.getNumStr(),
        'vote_time' : vote.getDate(),
        'vote_title' : vote.title,
        'vote_question' : vote.question,
        'vote_result' : vote.result,
        'congress' : congress_id,
        'yeas_list' : html_lists[1],
        'nays_list' : html_lists[0],
        'pres_list' : html_lists[2],
        'novt_list' : html_lists[3],
        'yeas_cnts' : dict(partyCountsbyVote[1]),
        'nays_cnts' : dict(partyCountsbyVote[0]),
        'pres_cnts' : dict(partyCountsbyVote[2]),
        'novt_cnts' : dict(partyCountsbyVote[3]),
        'yeas_cnt' : counts[1],
        'nays_cnt' : counts[0],
        'pres_cnt' : counts[2],
        'novt_cnt' : counts[3],
        'geoids' : geoids,
        'values' : values,
        'cloro_text' : text,
        'is_house' : isHouseVote
    }
    return context


####
##  These functions return an html table of a given queryset, with links when appropriate
##  Not done on JS because we need to access django model data anyways
####
def _action_badge_type(action):
    """Map a Congress API action dict to one of the badge type keys."""
    if 'recordedVotes' in action:
        return 'vote'
    code = action.get('actionCode', '')
    if code in ('1000', '10000'):
        return 'intro'
    a_type = action.get('type', '')
    if a_type in ('Floor', 'Calendars', 'BecameLaw', 'President', 'Discharge'):
        return 'floor'
    if a_type == 'Committee':
        text = action.get('text', '').lower()
        if 'markup' in text:
            return 'markup'
        if 'report' in text:
            return 'report'
        return 'referral'
    return 'referral'

_BADGE_LABELS = {
    'vote': 'Vote',
    'intro': 'Intro',
    'floor': 'Floor',
    'referral': 'Referral',
    'report': 'Report',
    'markup': 'Markup',
}

async def actionTable(act_list, bill_type, bill_num):
    """Build a styled action timeline table."""
    actions = act_list.get('actions', [])

    # Batch-collect vote ids so we can build links without per-row DB queries
    vote_id_map = {}
    for idx, action in enumerate(actions):
        if 'recordedVotes' in action:
            rv = action['recordedVotes'][0]
            in_house = 0 if rv.get('chamber') != 'House' else 1
            try:
                vote_id = (rv.get('congress', 0) * 10000000
                           + in_house * 1000000
                           + int(rv.get('sessionNumber', 0)) * 100000
                           + int(rv.get('rollNumber', 0)))
            except Exception:
                continue
            vote_id_map.setdefault(vote_id, []).append(idx)

    existing_vote_ids = set()
    if vote_id_map:
        qs = Vote.objects.filter(id__in=list(vote_id_map.keys())).values_list('id', flat=True)
        existing_vote_ids = set(await sync_to_async(list)(qs))

    parts = [
        '<table class="action-table">'
        '<thead><tr>'
        '<th>Action Date</th><th>Type</th><th>Text</th><th>Source</th>'
        '</tr></thead><tbody>'
    ]

    for action in actions:
        ss = action.get('sourceSystem', {})
        if ss.get('code') == 9 and action.get('actionCode') not in {'1000', '10000', 'E30000', 'E40000'}:
            continue

        badge_key = _action_badge_type(action)
        badge_label = _BADGE_LABELS[badge_key]
        date_str = action.get('actionDate', '')
        text = action.get('text', '')
        source = ss.get('name', '')

        parts.append(f'<tr>')
        parts.append(f'<td class="action-date">{date_str}</td>')

        if badge_key == 'vote' and 'recordedVotes' in action:
            rv = action['recordedVotes'][0]
            in_house = 0 if rv.get('chamber') != 'House' else 1
            try:
                vote_id = (rv.get('congress', 0) * 10000000
                           + in_house * 1000000
                           + int(rv.get('sessionNumber', 0)) * 100000
                           + int(rv.get('rollNumber', 0)))
                parts.append(f'<td><a class="action-badge action-badge--vote" href="/vote/{vote_id}">{badge_label}</a></td>')
            except Exception:
                parts.append(f'<td><span class="action-badge action-badge--{badge_key}">{badge_label}</span></td>')
        else:
            parts.append(f'<td><span class="action-badge action-badge--{badge_key}">{badge_label}</span></td>')

        parts.append(f'<td class="action-text">{text}</td>')
        parts.append(f'<td class="action-source">{source}</td>')
        parts.append('</tr>')

    parts.append('</tbody></table>')
    return ''.join(parts)

def billTable(bill_list):
    """
    Produce an HTML table of bills.
    - Use list append + join to reduce string concatenation overhead.
    """
    parts = [
        '<table class="table table-bordered table-small dark-1">'
        '<thead><tr><th>Origin Date</th><th>Latest Action</th><th>Bill ID</th><th>Title</th><th>Source</th></tr></thead><tbody>'
    ]
    for bill in bill_list:
        od = bill.origin_date
        la = bill.latest_action
        parts.append(
            '<tr><td>{}/{}/{}</td>'.format(od.month, od.day, od.year)
        )
        parts.append(
            '<td>{}/{}/{}</td>'.format(la.month, la.day, la.year)
        )
        parts.append(
            '<td><a href="/bill/{}">{}</a></td>'.format(bill.getURL(), bill.__str__())
        )
        parts.append('<td>{}</td>'.format(bill.title))
        parts.append('<td>{}</td></tr>'.format(bill.getOrigin()))
    parts.append('</tbody></table>')
    return ''.join(parts)

def voteTablePage(vote_list):
    """
    Produce an HTML table of votes for page listing.
    - Use list append + join.
    """
    parts = [
        '<table class="table table-bordered table-small dark-1">'
        '<thead><tr><th>Date</th><th>Vote</th><th>Bill</th><th>Result</th></tr></thead><tbody>'
    ]
    for vote in vote_list:
        parts.append('<tr><td>{}</td>'.format(vote.getDate()))
        parts.append('<td><a href="/vote/{}">{}</a></td>'.format(vote.id, vote.question))
        parts.append('<td><a href="/bill/{}">{}</a></td>'.format(vote.bill.getURL(), vote.bill.__str__()))
        parts.append('<td>{}</td></tr>'.format(vote.result))
    parts.append('</tbody></table>')
    return ''.join(parts)

def voteTable(vote_list, membership):
    """
    Produce a per-member vote table.
    - Cache membership lookup once to reduce repeated DB hits.
    - Use list append + join for efficient string assembly.
    """

    vote_ids = [v.id for v in vote_list]
    if membership and vote_ids:
        yea_ids = set(Vote.objects.filter(id__in=vote_ids, yeas=membership).values_list('id', flat=True))
        nay_ids = set(Vote.objects.filter(id__in=vote_ids, nays=membership).values_list('id', flat=True))
        pres_ids = set(Vote.objects.filter(id__in=vote_ids, pres=membership).values_list('id', flat=True))
    else:
        yea_ids = nay_ids = pres_ids = set()

    parts = [
        '<table class="action-table">'
        '<thead><tr>'
        '<th>Vote Date</th><th>Bill</th><th>Question</th><th>Vote</th>'
        '</tr></thead><tbody>'
    ]
    badge_map = {'Yea': 'passed', 'Nay': 'failed', 'Present': 'other', 'No Vote': 'other'}
    for vote in vote_list:
        bill = vote.bill

        if vote.id in yea_ids:
            vote_type = 'Yea'
        elif vote.id in nay_ids:
            vote_type = 'Nay'
        elif vote.id in pres_ids:
            vote_type = 'Present'
        else:
            vote_type = 'No Vote'

        badge_cls = badge_map.get(vote_type, 'other')
        parts.append('<tr>')
        parts.append(f'<td><span class="action-date">{vote.getDate()}</span></td>')
        parts.append(f'<td><a href="/bill/{bill.getURL()}" class="rep-vote-link">{bill.__str__()}</a></td>')
        parts.append(f'<td class="action-text"><a href="/vote/{vote.id}">{vote.question}</a></td>')
        parts.append(f'<td><span class="vote-result-badge vote-result-badge--{badge_cls}">{vote_type}</span></td>')
        parts.append('</tr>')
    parts.append('</tbody></table>')
    return ''.join(parts)

def partyList(party_history):
    _party_cls = {'Republican': 'r', 'Democrat': 'd', 'Democratic': 'd', 'Independent': 'i'}
    parts = []
    for history in party_history:
        start = history.get('startYear', '')
        end = history.get('endYear', 'Present')
        party_name = history.get('partyName', '')
        cls = _party_cls.get(party_name, 'other')
        parts.append(
            f'<div class="rep-party-row rep-party-row--{cls}">'
            f'<span class="rep-party-name">{party_name}</span>'
            f'<span class="rep-party-period">{start}-{end}</span>'
            f'</div>'
        )
    return ''.join(parts)

def leadershipList(leaderships):
    parts = []
    for leadership in leaderships:
        parts.append(
            '<li class="list-group-item bg-trans darkmode">{cong}{suf} Congress : {type}</li>'.format(
                cong=leadership.get('congress'), suf=getNumSuffix(leadership.get('congress')), type=leadership.get('type', '')
            )
        )
    return ''.join(parts)

def termList(terms, bioguideID, congress_num):
    parts = []
    for term in reversed(terms):
        num = term['congress']
        district = ''
        if 'district' in term:
            district = f', {term["district"]}{getNumSuffix(term["district"])} District'

        is_current = int(num) == int(congress_num)
        current_class = ' rep-term-row--current' if is_current else ''
        congress_label = f'{num}{getNumSuffix(int(num))} Congress'
        role_text = f'{term.get("memberType")} of {term.get("stateName")}{district}'
        period_end = str(term.get('endYear')) if 'endYear' in term else 'Present'
        period = f'{term.get("startYear")}-{period_end}'

        try:
            has_link = int(num) >= 112
        except Exception:
            has_link = False

        inner = (
            f'<div>'
            f'<div class="rep-term-congress">{congress_label}</div>'
            f'<div class="rep-term-role">{role_text}</div>'
            f'</div>'
            f'<span class="rep-term-period">{period}</span>'
        )

        if has_link:
            chamber = 'House+of+Representatives' if term.get('memberType') == 'Representative' else 'Senate'
            link_url = f'/member/results/?congress={num}&member={bioguideID}&chamber={chamber}'
            parts.append(f'<a href="{link_url}" class="rep-term-row{current_class}">{inner}</a>')
        else:
            parts.append(f'<div class="rep-term-row{current_class}">{inner}</div>')

    return ''.join(parts)

def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")