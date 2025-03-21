from datetime import datetime
import requests, asyncio, json, aiohttp
from requests.exceptions import HTTPError
from USQuery import settings
from SenateQuery.models import Member, Congress, Membership
from BillQuery.models import Bill, Vote
from asgiref.sync import sync_to_async
from collections import defaultdict
from xml.etree import cElementTree as ET

## helpful objects that map state related data
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

## connects to an API with given headers
def connect(fullpath, headers):
    try:
        response = requests.get(fullpath, headers, timeout=20)
        response.raise_for_status()
    except HTTPError as http_err:
        print(f'HTTP ERROR : {http_err}')
    except Exception as err:
        print(f'MISC ERROR : {err}')
    except TimeoutError:
        print('TIMEOUT ERROR')
    else:
        print('Connected to ' + fullpath)
        return response    

## connects to an API with given headers(in string format) asynchronously
## must specify if response is to be jsonified or not
async def connectASYNC(session, fullpath, header_str, jsonify = True):
    try:
        async with session.get(fullpath + header_str, timeout=40) as response:
            response.raise_for_status()
            print('Connected to ' + fullpath)
            if jsonify:
                return await response.json()
            else:
                return await response.text()
    except aiohttp.ClientError as http_err:
        print(f'HTTP ERROR : {http_err}')
    except json.JSONDecodeError as e:
        print("Invalid JSON syntax:", e)
    except Exception as err:
        print(f'MISC ERROR : {err} when connecting to {fullpath}')
    except asyncio.TimeoutError:
        print('TIMEOUT ERROR')

## returns a list of responses from a list of requests asynchronously
async def run_concurrent_connect(session, requests, headers) : 
    tasks = []
    for request in requests: 
        ret = connectASYNC(session, request, headers)
        tasks.append(ret)
    return await asyncio.gather(*tasks, return_exceptions=True)

## mega function to add members for a given congress
## to fully load a member we need to make an updateMember call adding image and other info
def addMembersCongressAPILazy(congress_num):
    headers = {
        'api_key' : settings.CONGRESS_KEY,
        'format' : 'json',
        'currentMember' : 'false',
        'offset' : '0', 'limit' : '250'
        }
    API_cong = connect(settings.CONGRESS_DIR + '/congress/' + str(congress_num), headers).json()
    start_date = API_cong['congress']['sessions'][0]['startDate']
    end_date = None if len(API_cong['congress']['sessions']) <= 2 else API_cong['congress']['sessions'][2]['endDate']
    API_response = connect(settings.CONGRESS_DIR + "/member/congress/" + str(congress_num), headers).json()
    congress = Congress.objects.get_or_create(
        congress_num = congress_num,
        start_year = int(API_cong['congress']['startYear']),
        end_year = int(API_cong['congress']['endYear'])
        )[0]
    
    while (API_response != None):
        for member in API_response['members']:
            _id=member['bioguideId']
            in_house = member['district'] != None
            district = None if not in_house else member['district']
            member_set = Member.objects.filter(id = _id)
            if member_set.exists() and Membership.objects.filter(congress = congress, member = member_set[0], house = in_house).exists():
                continue    
            name = getFirstAndLastName(member['name'])
            full_name = name[0] + " "  + name[1]
            if (member_set.exists()):
                _member = member_set[0]
            else :
                _member = Member.objects.get_or_create(
                    id = _id, 
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
            print("added member " + _id)
        if 'next' in API_response['pagination']:
            API_response = connect(API_response['pagination']['next'], {'api_key' : settings.CONGRESS_KEY}).json()
        else : API_response = None

## swap membership given bioguide_ids and dates of arrival and departure
## if departing member has no succesor, arriving_id should be "!"
def swapMembership(congress_num, leaving_id, in_house, leaving_date, arriving_id, arriving_date, party) :
    in_house = (in_house == 1)
    _congress = Congress.objects.get(congress_num__exact = congress_num)
    leaving_member = Member.objects.get(id = leaving_id)
    leaving_membership = Membership.objects.get(congress = _congress, member = leaving_member, house = in_house)       
    if (arriving_id != "!") :
        _set_member = Member.objects.filter(id = arriving_id)
        if (_set_member.exists()):
            arriving_member = _set_member[0]
        else :
            API_response_member = connect(settings.CONGRESS_DIR + 'member/' + arriving_id).json()
            arriving_member = Member.objects.get_or_create(
                id = arriving_id, 
                full_name = API_response_member['member']['directOrderName'],
                first_name = API_response_member['member']['firstName'],
                last_name = API_response_member['member']['lastName'],
                image_link = "empty"
                )[0]
        arriving_membership = Membership.objects.get_or_create(
            congress = _congress,
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
    _congress = Congress.objects.get(congress_num__exact = congress_id)
    _member = Member.objects.get(id = arriving_id)
    _membership = Membership.objects.get(congress = _congress, member = _member, house = in_house)       
    _membership.start_date = arriving_date
    _membership.save()

## creates a new membership with all required parameters (beyond arrival date is optional)
## DANGEROUS: will create a new membership even if one already exists if there is a slight
## variation from extant membership (ex: mistyped party)
def createMembership(congress_id, member_id, state, in_house, party, arrival_date, departure_date, district_num) :
    in_house = (in_house == 1) 
    _congress = Congress.objects.get(congress_num__exact = congress_id)
    _member = Member.objects.get(id = member_id)
    _membership = Membership.objects.get_or_create(
            congress = _congress,
            member = _member,
            district_num = district_num,
            house = in_house,
            state = state,
            geoid = state_fips[state] + ('' if not in_house else intToFIPS(district_num)),
            party = party ,
            start_date = arrival_date,
            end_date = departure_date
            )[0]
    _membership.start_date = arrival_date
    _membership.end_date = departure_date
    _membership.save()

## updates database, adding new bills or updating bills and votes with actionDate GTE current_date_str
async def updateRecentBills(congress_num, current_date_str, bill_type):
    header_str = '&api_key=' + settings.CONGRESS_KEY + '&format=json&limit=250'
    session = aiohttp.ClientSession()
    vote_session = aiohttp.ClientSession()
    _congress = await sync_to_async(Congress.objects.get)(congress_num__exact = congress_num)
    current_date = datetime.strptime(current_date_str, '%Y-%m-%d')
    API_response = await connectASYNC(session, settings.CONGRESS_DIR + "bill/" + str(congress_num) + "/" + bill_type + "?", header_str)
    
    while API_response is not None:
        for bill in API_response['bills']:
            latest_action_date = datetime.strptime(bill['latestAction']['actionDate'], '%Y-%m-%d')
            if latest_action_date >= current_date:
                await addBillASYNC(session, vote_session, congress_num, bill_type, bill, _congress, header_str, False)
        if 'next' in API_response['pagination']:
            API_response = await connectASYNC(session, API_response['pagination']['next'], header_str)
        else:
            API_response = None
    await session.close()
    await vote_session.close()

## mega function that creates bills, and creates any votes for a given bill
## too many api calls will lead to being blocked by congress api
async def addBills(congress_num = 116, _type='s', limit = 100, offset = 0):
    header_str_sp = '&api_key=' + settings.CONGRESS_KEY + '&format=json&limit=' + str(limit) + '&offset=' + str(offset)
    header_str = '&api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=250'
    session = aiohttp.ClientSession()
    vote_session = aiohttp.ClientSession()
    API_response = await connectASYNC(session, settings.CONGRESS_DIR + "bill/" + str(congress_num) + "/" + _type + "?", header_str_sp)
    _congress = await sync_to_async(Congress.objects.get)(congress_num__exact = congress_num)
    
    indx = 0
    limit = 5
    n = len(API_response['bills'])
    
    while (indx < n) : 
        end = min (indx + limit, n)
        sets = API_response['bills'][indx:end]
        async with asyncio.TaskGroup() as tg:
            for bill in sets:
                tg.create_task(addBillASYNC(session, vote_session, congress_num, _type, bill, _congress, header_str))
        indx = end
    print('added up to ' + str(offset + indx))
    if 'next' in API_response['pagination']:
        print(', need to get to ' + str(API_response['pagination']['count']))
    await session.close()
    await vote_session.close()

async def updateBill(congress_num, _type, _num) :
    url = settings.CONGRESS_DIR + 'bill/' + str(congress_num) + '/' + _type + '/' + str(_num) + '/actions?'
    header_str = '&api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=250'
    session = aiohttp.ClientSession()
    vote_session = aiohttp.ClientSession()
    if (int(_num) < 10000):
        _id = congress_num * 100000 + types[_type] * 10000 + int(_num)
    else :
        _id = congress_num * 1000000 + types[_type] * 100000 + int(_num)
    _congress = await sync_to_async(Congress.objects.get)(congress_num__exact = congress_num)
    _bill = await sync_to_async(Bill.objects.get)(id__exact = _id)    
    
    API_response_actions = await connectASYNC(session, url, header_str)
    while API_response_actions is not None:
        for a in API_response_actions['actions']:
            if 'recordedVotes' in a:
                in_house = 0 if (a['recordedVotes'][0]['chamber'] != 'House') else 1
                vote_id = congress_num * 10000000 + in_house * 1000000 + int(a['recordedVotes'][0]['sessionNumber']) * 100000 + int(a['recordedVotes'][0]['rollNumber'])
                try:
                    vote_xml = await connectASYNC(vote_session, a['recordedVotes'][0]['url'], '', False)
                    vote_xml = ET.XML(vote_xml)
                except aiohttp.ClientConnectionError as e:
                    print(f"Connection error: {e}")
                    return
                vote_dict = etree_to_dict(vote_xml)    
                vote_data = {
                    'id': vote_id,
                    'congress': _congress,
                    'house': in_house == 1,
                    'bill' : _bill,
                    'dateTime': a['recordedVotes'][0]['date'],
                    'question': vote_dict['rollcall-vote']['vote-metadata']['vote-question'] if in_house == 1 else vote_dict['roll_call_vote']['question'],
                    'title': vote_dict['rollcall-vote']['vote-metadata']['vote-desc'] if in_house == 1 else vote_dict['roll_call_vote']['vote_title'],
                    'result': vote_dict['rollcall-vote']['vote-metadata']['vote-result'] if in_house == 1 else vote_dict['roll_call_vote']['vote_result']
                }
                _vote = await sync_to_async(Vote.objects.get_or_create)(**vote_data)
                _vote = _vote[0]
                members = vote_dict['rollcall-vote']['vote-data']['recorded-vote'] if in_house == 1 else vote_dict['roll_call_vote']['members']['member']
                member_votes = {
                    'Yea': _vote.yeas,
                    'Nay': _vote.nays,
                    'Not Voting': _vote.novt,
                    'Present': _vote.pres
                }
                q_sets = {
                    'Yea': await sync_to_async(Membership.objects.none)(),
                    'Aye': await sync_to_async(Membership.objects.none)(),
                    'Guilty' : await sync_to_async(Membership.objects.none)(),
                    'Nay': await sync_to_async(Membership.objects.none)(),
                    'No': await sync_to_async(Membership.objects.none)(),
                    'Not Guilty' : await sync_to_async(Membership.objects.none)(),
                    'Not Voting': await sync_to_async(Membership.objects.none)(),
                    'Present': await sync_to_async(Membership.objects.none)()
                }
                keys = ['Yea', 'Nay', 'Not Voting', 'Present']
                for m in members:
                    if (in_house == 1):
                        member = await sync_to_async(Membership.objects.filter)(congress=_congress, member__id=m['legislator']['@name-id'], house = True)
                    else :
                        member = await sync_to_async(Membership.objects.filter)(
                            congress=_congress,
                            house = False,
                            member__last_name__iexact=m['last_name'],
                            state=m['state']
                            )
                    q_sets[m['vote'] if in_house == 1 else m['vote_cast']] |= member
                q_sets['Yea'] |= q_sets['Aye'] | q_sets['Guilty']
                q_sets['Nay'] |= q_sets['No'] | q_sets['Not Guilty']
                for key in keys:
                    await sync_to_async(member_votes[key].set)(q_sets[key])
                print('Added Vote : ' + str(vote_id))
        if 'next' in API_response_actions['pagination']:
            API_response_actions = await connectASYNC(session, API_response_actions['pagination']['next'], header_str)
        else:
            API_response_actions = None
    await session.close()
    await vote_session.close()

# meant to be used asynchronously to add batches of bills at one time
async def addBillASYNC(session, vote_session, congress_num, _type, b, _congress, header_str, ignore_exists = True):
    if (int(b['number']) < 10000):
        _id = congress_num * 100000 + types[_type] * 10000 + int(b['number'])
    else :
        _id = congress_num * 1000000 + types[_type] * 100000 + int(b['number'])
        ignore_exists = False;
    _set_bill = await sync_to_async(Bill.objects.filter)(id = _id)    
    bill_exists = await sync_to_async(_set_bill.exists)()
    if (bill_exists and ignore_exists): return
    API_response_bill = await connectASYNC(session, b['url'], header_str)
    if (API_response_bill['bill']['title'][:8] == 'Reserved'):
        return # reserved bills are trivial, so we ignore them if their title was a reservation
    API_response_actions = await connectASYNC(session, API_response_bill['bill']['actions']['url'], header_str)
    _member = await sync_to_async(Member.objects.get)(id=API_response_bill['bill']['sponsors'][0]['bioguideId'])
    date = API_response_bill['bill']['introducedDate'].split('-')
    _membership = await sync_to_async(Membership.objects.get)(congress=_congress, member=_member, start_date__lte = datetime(int(date[0]), int(date[1]), int(date[2])))
    _status = ('laws' in API_response_bill['bill']) and (len(API_response_bill['bill']['laws']) > 0)

    if (bill_exists) : 
        _bill = await sync_to_async(Bill.objects.get)(id = _id)
        _bill.title = b['title']
        _bill.status = _status
        _bill.latest_action = API_response_bill['bill']['latestAction']['actionDate']
        await sync_to_async(_bill.save)()
    else :
        _bill = await sync_to_async(Bill.objects.get_or_create)(
            id = _id,
            title = b['title'],
            sponsor = _membership,
            status = _status,
            origin_date = API_response_bill['bill']['introducedDate'],
            latest_action = API_response_bill['bill']['latestAction']['actionDate']
            )
        _bill = _bill[0]

    while API_response_actions is not None:
        for a in API_response_actions['actions']:
            if 'recordedVotes' in a:
                in_house = 0 if (a['recordedVotes'][0]['chamber'] != 'House') else 1
                vote_id = congress_num * 10000000 + in_house * 1000000 + int(a['recordedVotes'][0]['sessionNumber']) * 100000 + int(a['recordedVotes'][0]['rollNumber'])
                _set_vote = await sync_to_async(Vote.objects.filter)(id = vote_id)
                if ignore_exists and (await sync_to_async(_set_vote.exists)()):
                    return
                try:
                    vote_xml = await connectASYNC(vote_session, a['recordedVotes'][0]['url'], '', False)
                    vote_xml = ET.XML(vote_xml)
                except aiohttp.ClientConnectionError as e:
                    print(f"Connection error: {e}")
                    return
                vote_dict = etree_to_dict(vote_xml)    
                vote_data = {
                    'id': vote_id,
                    'congress': _congress,
                    'house': in_house == 1,
                    'dateTime': a['recordedVotes'][0]['date'],
                    'question': vote_dict['rollcall-vote']['vote-metadata']['vote-question'] if in_house == 1 else vote_dict['roll_call_vote']['question'],
                    'title': vote_dict['rollcall-vote']['vote-metadata']['vote-desc'] if in_house == 1 else vote_dict['roll_call_vote']['vote_title'],
                    'result': vote_dict['rollcall-vote']['vote-metadata']['vote-result'] if in_house == 1 else vote_dict['roll_call_vote']['vote_result']
                }
                _vote, created = await sync_to_async(Vote.objects.get_or_create)(**vote_data)
                if created or not ignore_exists:
                    _vote.bill = _bill
                    await sync_to_async(_vote.save)()
                    members = vote_dict['rollcall-vote']['vote-data']['recorded-vote'] if in_house == 1 else vote_dict['roll_call_vote']['members']['member']
                    member_votes = {
                        'Yea': _vote.yeas,
                        'Nay': _vote.nays,
                        'Not Voting': _vote.novt,
                        'Present': _vote.pres
                    }
                    q_sets = {
                        'Yea': await sync_to_async(Membership.objects.none)(),
                        'Aye': await sync_to_async(Membership.objects.none)(),
                        'Guilty' : await sync_to_async(Membership.objects.none)(),
                        'Nay': await sync_to_async(Membership.objects.none)(),
                        'No': await sync_to_async(Membership.objects.none)(),
                        'Not Guilty' : await sync_to_async(Membership.objects.none)(),
                        'Not Voting': await sync_to_async(Membership.objects.none)(),
                        'Present': await sync_to_async(Membership.objects.none)()
                    }
                    keys = ['Yea', 'Nay', 'Not Voting', 'Present']
                    for m in members:
                        if (in_house == 1):
                            member = await sync_to_async(Membership.objects.filter)(congress=_congress, member__id=m['legislator']['@name-id'], house = True)
                        else :
                            member = await sync_to_async(Membership.objects.filter)(
                                congress=_congress,
                                house = False,
                                member__last_name__iexact=m['last_name'],
                                state=m['state']
                                )
                        q_sets[m['vote'] if in_house == 1 else m['vote_cast']] |= member
                    q_sets['Yea'] |= q_sets['Aye'] | q_sets['Guilty']
                    q_sets['Nay'] |= q_sets['No'] | q_sets['Not Guilty']
                    for key in keys:
                        await sync_to_async(member_votes[key].set)(q_sets[key])
                    print('Added Vote : ' + str(vote_id))
        if 'next' in API_response_actions['pagination']:
            API_response_actions = await connectASYNC(session, API_response_actions['pagination']['next'], header_str)
        else:
            API_response_actions = None
    return 1

# runs through existing votes up to limit, and adds memberships that were missing
async def fixHouseVotes(congress_num, year, nums, member_ids) : 
    session = aiohttp.ClientSession()
    congress = await sync_to_async(Congress.objects.get)(congress_num__exact = congress_num)
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
    _set_vote = await sync_to_async(Vote.objects.filter)(id = vote_id)
    if await sync_to_async(_set_vote.exists)():
        vote = await sync_to_async(Vote.objects.get)(id = vote_id)
        try:
            vote_xml = await connectASYNC(session, url, '', False)
            vote_xml = ET.XML(vote_xml)
        except aiohttp.ClientConnectionError as e:
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
                _set = await sync_to_async(member_votes[m['vote']].filter)(congress=congress, member__id=m['legislator']['@name-id'], house = True)
                if not await sync_to_async(_set.exists)() :
                    member = await sync_to_async(Membership.objects.get)(congress=congress, member__id=m['legislator']['@name-id'], house = True)
                    await sync_to_async(member_votes[m['vote']].add)(member)


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
    if (num % 10 == 1 and num // 10 != 1) : return 'rst'
    elif (num % 10 == 2 and num // 10 != 1) : return 'nd'
    elif (num % 10 == 3 and num // 10 != 1) : return 'rd'
    return 'th'

def findIndexOfRoleByChamberAndCongress(roles, congress_num, chamber):
    for i in range(len(roles)):
        if (roles[i]['congress'] == str(congress_num)) & (roles[i]['chamber'] == chamber): 
            return i
    return -1    
                    
def updateMember(congress_num, member_id): 
    _congress = Congress.objects.get(congress_num__exact = congress_num)    
    _member = Member.objects.get(id__exact = member_id)
    API_response_member = connect(_member.getAPIURL(), {'api_key' : settings.CONGRESS_KEY, 'format' : 'json'}).json()
    image_link = _member.image_link
    if image_link != "empty": return API_response_member
    
    office_addr = None
    phone_num = None
    death_year = None
    site = None
    
    if ('deathYear' in API_response_member['member']) :
        death_year = API_response_member['member']['deathYear']
        
    if (API_response_member['member']['currentMember']) :
        site = API_response_member['member']['officialWebsiteUrl']
        office_addr = API_response_member['member']['addressInformation']['officeAddress']
        phone_num = API_response_member['member']['addressInformation']['phoneNumber']

    ## find this term's party
    if (len(API_response_member['member']['partyHistory']) > 1):
        _membership = Membership.objects.get(congress = _congress, member = _member)
        for hist in API_response_member['member']['partyHistory']:
            if (hist['startYear'] < _congress.end_year and ('endYear' not in hist or hist['endYear'] > _congress.start_year)):
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
    return API_response_member;

def getBillsInRange(s_d, e_d):
    start = s_d.split('-')
    end = e_d.split('-')
    start_date = datetime(int(start[0]), int(start[1]), int(start[2]))
    end_date = datetime(int(end[0]), int(end[1]), int(end[2]))
    return Bill.objects.filter(latest_action__gte=start_date, latest_action__lte=end_date)

def intToFIPS(num):
    if num < 10 : return '0' + str(num)
    return str(num)
#### 
##  return a context for http request to fill html page with content
####
async def billHtml(congress_id, bill_type, num):
    apiURL = settings.CONGRESS_DIR + "bill/" + congress_id + "/" + bill_type + "/" + num
    requests = [apiURL, apiURL + '/actions', apiURL + '/cosponsors', apiURL + '/relatedbills', apiURL + '/subjects', apiURL + '/summaries']
    header_str = '?api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=250'
    session = aiohttp.ClientSession()
    API_data = await run_concurrent_connect(session, requests, header_str)
    
    context = {'title':"CONGRESS: " + congress_id + ", " + bill_type.upper() + "-" + num,
            'bill' : bill_type.upper() + "-" + num,
            }
    if ('actionCode' in API_data[1]['actions'][0]) and (API_data[1]['actions'][0]['actionCode'] in ['E40000', '36000']) :
        context['bill_state_type'] = 'Became Public Law'
    else :
        context['bill_state_type'] = 'Still Just a Bill'
      
    context['actions_table'] = await actionTable(API_data[1], bill_type, num)
        
    # Handles sponsors and cosponsors
    list_start = '<li class="list-group-item bg-trans darkmode"><a href="'
    member_link = '/member-query/results/?congress='
    bill_link = '/bill-query/results/bill/'
    q_2 = '&member='
    q_3 = '&chamber='

    sponsor = API_data[0]['bill']['sponsors'][0]
    if ('district' in sponsor) :  chamber = 'House+of+Representatives'
    else: 
        chamber = 'Senate' 
    context['sponsor'] = '<a href="' + member_link  + congress_id + q_2 + sponsor['bioguideId'] + q_3 + chamber + '" >' + sponsor['fullName'] + '</a>'

    if (API_data[2] != ''):
        co_list = ''
        for c in API_data[2]['cosponsors']:
            if ('district' in c) :  chanber = 'House+of+Representatives'
            else: chamber = 'Senate' 
            co_list += list_start + member_link + congress_id + q_2 + c['bioguideId'] + q_3 + chamber + '" >' + c['fullName'] + '</a></li>'
        context['cosponsors'] = co_list
        
    if (API_data[3] != ''):
        related_bills = ''
        for b in API_data[3]['relatedBills'] : 
            related_bills += list_start + bill_link + str(b['congress']) + '/' + b['type'].lower() + '/' + str(b['number']) + '" >' + b['type'] + '-' + str(b['number']) + '</a></li>'
        context['related_bills'] = related_bills
                  
    if (API_data[4] != ''):
        sub_list = ''
        for s in API_data[4]['subjects']['legislativeSubjects']:
            sub_list +=  '<li class="list-group-item bg-trans darkmode">' + s['name'] + '</li>'
        context['subjects'] = sub_list
        context['policy_area'] = 'Not Specified Yet.' if not ('policyArea' in API_data[4]['subjects']) else API_data[4]['subjects']['policyArea']['name']
            
    # currently jut gets first summary in list...
    if (API_data[5] != ''):
        context['summary'] = 'No Summary Provided Yet.' if (len(API_data[5]['summaries']) < 1) else API_data[5]['summaries'][0]['text']
        
    #if ('textVersions' in API_response['bill']):
     #   API_committees= connect(API_response['bill']['textVersions']['url'], headers).json()
    await session.close()
    return context

def voteHtml(vote):
    congress_id = vote.congress.__str__()
    q_2 = '&member='
    q_3 = '&chamber='
       
    votes_list = [vote.nays, vote.yeas, vote.pres, vote.novt]
    list_color = {
        'Democratic': ' dem',
        'Republican': ' rep',
        'Independent': ' ind',
        'Libertarian': ' lib',
        'Green': ' grn'
        }
    list_party = {
        'Democratic': ' [D]',
        'Republican': ' [R]',
        'Independent': ' [I]',
        'Libertarian': ' [L]',
        'Green': ' [G]'
        }
    html_lists = ['', '', '', '']
    partyCountsbyVote = [{}, {}, {}, {}]
    isHouseVote = vote.house
    j = 0
    if isHouseVote:
        mult = 435
        temp = int(congress_id)
        temp -= (temp % 2)
        geojson_source = 'geojsons/cb_us_cd' + str(temp) + '_5m.js'
        geojson_load = 'scripts/loadCounty.js'
        values = [0] * mult
        text = [''] * mult
    else :
        mult = 50
        geojson_source = 'geojsons/cb_us_state_5m.js'
        geojson_load = 'scripts/loadState.js'
        values = [[0] * mult, [0] * mult, [0] * mult, [0] * mult]
        text = state_list

    geoids = [None] * mult
    #          0 : Nay, 1 : Yea, 2 : Present, 3 : No Vote
    for i in range(4):
        votes = votes_list[i].all()
        for membership in votes:
            if (membership.party not in partyCountsbyVote[i]) : partyCountsbyVote[i][membership.party] = 0
            partyCountsbyVote[i][membership.party] += 1
            if isHouseVote:
                text[j] = state_list[fips_to_count[membership.geoid[:2]]] + '-' + membership.geoid[2:]
                geoids[j] = membership.geoid
                values[j] = i
                j+=1
                chamber = 'House+of+Representatives'
            else:
                indx = fips_to_count[membership.geoid]
                if indx == None : continue
                geoids[indx] = membership.geoid
                values[i][indx] += 1
                chamber = 'Senate'
            html_lists[i] += '<tr class="' + list_color[membership.party]  + '"><td><a href="/member-query/results/?congress=' 
            html_lists[i] += congress_id  + q_2 + membership.member.id + q_3 + chamber + '" class="link-light">' + membership.member.full_name + list_party[membership.party] + '</a></td></tr>'
                
        
    context = {'title': str(vote.id),
            'bill' : vote.bill.__str__(),
            'bill_title' : vote.bill.title,
            'bill_link' : '/bill-query/results/bill/' + congress_id  + '/' + vote.bill.getTypeURL() + '/' + vote.bill.getNumStr(),
            'vote_time' : vote.getDate(),
            'vote_title' : vote.title,
            'vote_question' : vote.question,
            'vote_result' : vote.result,
            'congress' : congress_id,
            'yeas_list' : html_lists[1],
            'nays_list' : html_lists[0],
            'pres_list' : html_lists[2],
            'novt_list' : html_lists[3],
            'yeas_cnts' : partyCountsbyVote[1],
            'nays_cnts' : partyCountsbyVote[0],
            'pres_cnts' : partyCountsbyVote[2],
            'novt_cnts' : partyCountsbyVote[3],
            'yeas_cnt' : votes_list[1].count(),
            'nays_cnt' : votes_list[0].count(),
            'pres_cnt' : votes_list[2].count(),
            'novt_cnt' : votes_list[3].count(),
            'geojson_source' : geojson_source,
            'geojson_load' : geojson_load,
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
async def actionTable(act_list, bill_type, bill_num):
    tableHTML = '<table class="table table-bordered table-small dark-1"><thead><tr><th>Action Date</th><th>Type</th><th>Text</th><th>Source</th></tr></thead><tbody>'
    for action in act_list['actions']:
        #check if action is ignorable
        if ('code' in action['sourceSystem'] and action['sourceSystem']['code'] == 9) and not (action['actionCode'] in ['1000', '10000', 'E30000', 'E40000']):
            continue
        tableHTML += '<tr><td>' + action['actionDate'] + '</td>';
        if ('recordedVotes' in action) :
            in_house = 0 if (action['recordedVotes'][0]['chamber'] != 'House') else 1
            vote_id = action['recordedVotes'][0]['congress'] * 10000000 + in_house * 1000000 + int(action['recordedVotes'][0]['sessionNumber']) * 100000 + int(action['recordedVotes'][0]['rollNumber'])
            _set = Vote.objects.filter(id = vote_id)
            if not await sync_to_async(_set.exists)() : 
                print("MISSING VOTES")
                await updateBill(action['recordedVotes'][0]['congress'], bill_type, bill_num)
            tableHTML += '<td><a href="/bill-query/vote/' + str(vote_id) + '">' + 'Vote' + '</a></td>';    
        else : 
            tableHTML += '<td>' + action['type'] + '</td>';
        tableHTML += '<td>' + action['text'] + '</td><td>' + action['sourceSystem']['name'] + '</td></tr>';
    tableHTML += '</tbody></table>';
    return tableHTML

def billTable(bill_list):
    tableHTML = '<table class="table table-bordered table-small dark-1"><thead><tr><th>Origin Date</th><th>Latest Action</th><th>Bill ID</th><th>Title</th><th>Source</th></tr></thead><tbody>'
    for bill in bill_list:
        tableHTML += '<tr><td>' + str(bill.origin_date.month) + "/" + str(bill.origin_date.day) + "/" + str(bill.origin_date.year) + '</td>';
        tableHTML += '<td>' + str(bill.latest_action.month) + "/" + str(bill.latest_action.day) + "/" + str(bill.latest_action.year) + '</td>';
        tableHTML += '<td><a href="bill/' + str(bill.getCongress()) + '/' + bill.getTypeURL() + '/' + str(bill.getNum()) + '">' + bill.__str__() + '</a></td>';
        tableHTML += '<td>' + bill.title + '</td>';
        tableHTML += '<td>' + bill.getOrigin() + '</td></tr>';
    tableHTML += '</tbody></table>';
    return tableHTML

def voteTable(vote_list, bioguideID, congress_num):
    _congress = Congress.objects.get(congress_num__exact = congress_num)    
    _member = Member.objects.get(id__exact = bioguideID)
    tableHTML = '<table class="table table-bordered table-small dark-1"><thead><tr><th>Vote Date</th><th>Bill</th><th>Question</th><th>Vote</th></tr></thead><tbody>'
    colors = ['yeas', 'nays', 'pres', 'novt']
    vote_type = ['Yea', 'Nay', 'Present', 'No Vote']
    for vote in vote_list:
        bill = vote.bill
        i = 3
        if vote.yeas.filter(congress = _congress, member = _member).exists():
            i = 0
        elif vote.nays.filter(congress = _congress, member = _member).exists():
            i = 1
        elif vote.pres.filter(congress = _congress, member = _member).exists():
            i = 2
        tableHTML += '<tr class="' + colors[i] + '"><td>' + vote.getDate() + '</td>';
        tableHTML += '<td><a href="/bill-query/results/bill/' + str(bill.getCongress()) + '/' + bill.getTypeURL() + '/' + str(bill.getNum()) + '" class="link-light">' + bill.__str__() + '</a></td>';
        tableHTML += '<td><a href="/bill-query/vote/' + str(vote.id) +  '" class="link-light">' + vote.question + '</a></td>';
        tableHTML += '<td>' + vote_type[i] + '</td></tr>';
    tableHTML += '</tbody></table>';
    return tableHTML
    
def partyList(party_history):
    party_list = ''
    for history in party_history:
        party_list += '<li class="list-group-item bg-trans darkmode">' + history['partyName'] + ' (' + str(history['startYear']) + '-'
        if ('endYear' in history) : party_list += str(history['endYear'])
        else : party_list += 'Present'
        party_list += ')</li>'
    return party_list

def leadershipList(leaderships):
    leadership_list = ''
    for leadership in leaderships:
        leadership_list += '<li class="list-group-item bg-trans darkmode">' + str(leadership['congress']) + getNumSuffix(leadership['congress'])
        leadership_list += ' Congress : ' + leadership['type']+ '</li>'
    return leadership_list
  
link_dict = {'Senator' : 'Senate', 'Representative' : 'House+of+Representatives'}

def termList(terms, bioguideID, congress_num):
    term_list = ''
    for term in reversed(terms):
        num = term['congress']
        link = '/member-query/results/?congress=' + str(num) + '&member=' + bioguideID + '&chamber='
        district = ''
        if ('district' in term):
            district = ', '  + str(term['district']) + getNumSuffix(term['district']) + ' District' 
            
        term_list += '<li class="list-group-item darkmode'
        if (term['congress'] == congress_num): term_list += ' dark-2' 
        else : term_list += ' bg-trans'
        term_list += '">'  + str(num) + getNumSuffix(num) + ' Congress : '
        term_list += '<a href="' + link + link_dict[term['memberType']] + '">' + term['memberType'] + ' of ' + term['stateName'] + district + '</a>'
        term_list += '(' + str(term['startYear']) + '-'
        if ('endYear' in term) : term_list += str(term['endYear'])
        else : term_list += 'Present'
        term_list += ')</a></li>'
    return term_list
    