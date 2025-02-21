from argparse import RawDescriptionHelpFormatter
from datetime import datetime
from asyncio.windows_events import NULL
import requests, json, time, xmltodict, asyncio
from USQuery import settings
from requests.exceptions import HTTPError
from SenateQuery.models import Member, Congress, Membership
from BillQuery.models import Bill, Vote, ChoiceVote, Choice
import aiohttp
from asgiref.sync import sync_to_async

from collections import defaultdict
from xml.etree import cElementTree as ET
## https://stackoverflow.com/a/10077069

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

state_list = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
              'HI','ID','IN','IL','IA','KS','KY','LA','ME','MD',
              'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
              'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
              'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']

state_dict = {'AL' : 'Alabama',
              'AK' : 'Alaska',
              'AZ' : 'Arizona' ,
              'AR' : 'Arkansas',
              'CA' : 'California',
              'CO' : 'Colorado',
              'CT' : 'Connecticut',
              'DE' : 'Delaware',
              'FL' : 'Florida',
              'GA' : 'Georgia',
              'HI' : 'Hawaii',
              'ID' : 'Idaho',
              'IN' : 'Indiana',
              'IL' : 'Illinois',
              'IA' : 'Iowa',
              'KS' : 'Kansas',
              'KY' : 'Kentucky',
              'LA' : 'Louisiana',
              'ME' : 'Maine',
              'MD' : 'Maryland',
              'MA' : 'Massachusetts',
              'MI' : 'Michigan',
              'MN' : 'Minnesota',
              'MS' : 'Mississippi',
              'MO' : 'Missouri',
              'MT' : 'Montana',
              'NE' : 'Nebraska',
              'NV' : 'Nevada',
              'NH' : 'New Hampshire',
              'NJ' : 'New Jersey',
              'NM' : 'New Mexico',
              'NY' : 'New York',
              'NC' : 'North Carolina',
              'ND' : 'North Dakota',
              'OH' : 'Ohio',
              'OK' : 'Oklahoma',
              'OR' : 'Oregon',
              'PA' : 'Pennsylvania',
              'RI' : 'Rhode Island',
              'SC' : 'South Carolina',
              'SD' : 'South Dakota',
              'TN' : 'Tennessee',
              'TX' : 'Texas',
              'UT' : 'Utah',
              'VT' : 'Vermont',
              'VA' : 'Virginia',
              'WA' : 'Washington',
              'WV' : 'West Virginia',
              'WI' : 'Wisconsin',
              'WY' : 'Wyoming',
              'DC' : 'District of Columbia',
              'AS' : 'American Samoa',
              'GU' : 'Guam',
              'MP' : 'Northern Mariana Islands',
              'PR' : 'Puerto Rico',
              'VI' : 'Virgin Islands'
              }

reverse_state_dict = {'Alabama' : 'AL',
              'Alaska' : 'AK',
              'Arizona' : 'AZ',
              'Arkansas' : 'AR',
              'California' : 'CA',
              'Colorado' : 'CO',
              'Connecticut' : 'CT',
              'Delaware' : 'DE',
              'Florida' : 'FL',
              'Georgia' : 'GA',
              'Hawaii' : 'HI',
              'Idaho' : 'ID',
              'Indiana' : 'IN',
              'Illinois' : 'IL',
              'Iowa' : 'IA',
              'Kansas' : 'KS',
              'Kentucky' : 'KY',
              'Louisiana' : 'LA',
              'Maine' : 'ME',
              'Maryland' : 'MD',
              'Massachusetts' : 'MA',
              'Michigan' : 'MI',
              'Minnesota' : 'MN',
              'Mississippi' : 'MS',
              'Missouri' : 'MO',
              'Montana' : 'MT',
              'Nebraska' : 'NE',
              'Nevada' : 'NV',
              'New Hampshire' : 'NH',
              'New Jersey' : 'NJ',
              'New Mexico' : 'NM',
              'New York' : 'NY',
              'North Carolina' : 'NC',
              'North Dakota' : 'ND',
              'Ohio' : 'OH',
              'Oklahoma' : 'OK',
              'Oregon' : 'OR',
              'Pennsylvania' : 'PA',
              'Rhode Island' : 'RI',
              'South Carolina' : 'SC',
              'South Dakota' : 'SD',
              'Tennessee' : 'TN',
              'Texas' : 'TX',
              'Utah' : 'UT',
              'Vermont' : 'VT',
              'Virginia' : 'VA',
              'Washington' : 'WA',
              'West Virginia' : 'WV',
              'Wisconsin' : 'WI',
              'Wyoming' : 'WY',
              'District of Columbia' : 'DC',
              'American Samoa' : 'AS',
              'Guam' : 'GU',
              'Northern Mariana Islands' : 'MP',
              'Puerto Rico' : 'PR',
              'Virgin Islands' : 'VI'
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

types = {
            's' : 0,
            'sres' : 1,
            'sjres' : 2,
            'sconres' : 3,
            'hr' : 4,
            'hres' : 5,
            'hjres' : 6,
            'hconres' : 7}

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

async def connectASYNC(session, fullpath, header_str, jsonify = True):
    try:
        async with session.get(fullpath + header_str, timeout=40) as response:
            response.raise_for_status()
            print('Connected to ' + fullpath)
            if jsonify:
                return await response.json()
            else:
                return response
    except aiohttp.ClientError as http_err:
        print(f'HTTP ERROR : {http_err}')
    except Exception as err:
        print(f'MISC ERROR : {err} when connecting to {fullpath}')
    except asyncio.TimeoutError:
        print('TIMEOUT ERROR')

async def run_concurrent_connect(session, requests, headers) : 
    tasks = []
    for request in requests: 
        ret = connectASYNC(session, request, headers)
        tasks.append(ret)
    return await asyncio.gather(*tasks, return_exceptions=True)

## mega function to add members for a given congress, to fully load a member we need to make an updateMember call, which costs one api call...
def addMembersCongressAPILazy(congress_num):
    headers = {'api_key' : settings.CONGRESS_KEY, 'format' : 'json'}
    headers['curerentMember'] = 'false'
    headers['offset'] = '0'
    headers['limit'] = '250'
    
    API_cong = connect(settings.CONGRESS_DIR + '/congress/' + str(congress_num), headers).json()
    
    start_date = API_cong['congress']['sessions'][0]['startDate']
    end_date = API_cong['congress']['sessions'][2]['endDate']
    
    API_response = connect(settings.CONGRESS_DIR + "/member/congress/" + str(congress_num), headers).json()
    congress = Congress.objects.get_or_create(
        congress_num = congress_num,
        start_year = int(API_cong['congress']['startYear']),
        end_year = int(API_cong['congress']['endYear'])
        )[0]
    
    while (API_response != None):
        for member in API_response['members']:
            _id=member['bioguideId']
            district = None
            in_house = False  
            if (member['district'] != None):
                district = member['district']
                in_house = True
                
            _set = congress.members.filter(id = _id)
            if _set.exists() and Membership.objects.filter(congress = congress, member = _set[0]).exists():
                continue    
            #membership does not exist in congress so we search for member, if doesn't exist make new member
            name = getFirstAndLastName(member['name'])
            full_name = name[0] + " "  + name[1]
            _set_member = Member.objects.filter(id = _id)
            if (_set_member.exists()):
                _member = _set_member[0]
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
    return

## mega function that creates bills, and from bills creates votes
## too many api calls will lead to being blocked by congress api
## currently not optimized to ignore already added bills
async def addBills(congress_num = 116, _type='s', limit = 100, offset = 0):
    header_str_sp = '&api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=' + str(limit) + '&offset=' + str(offset)
    header_str = '&api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=250'
    session = aiohttp.ClientSession()
    vote_session = aiohttp.ClientSession()
    API_response = await connectASYNC(session, settings.CONGRESS_DIR + "bill/" + str(congress_num) + "/" + _type + "?", header_str_sp)
    _congress = await sync_to_async(Congress.objects.get)(congress_num__exact = congress_num)
    
    indx = 0
    limit = 10
    n = len(API_response['bills'])
    
    while (indx < n) : 
        end = min (indx + limit, n)
        sets = API_response['bills'][indx:end]
        async with asyncio.TaskGroup() as tg:
            for bill in sets:
                tg.create_task(addBillASYNC(session, vote_session, congress_num, _type, bill, _congress, header_str))
        indx = end
    await session.close()
    await vote_session.close()



async def addBillASYNC(session, vote_session, congress_num, _type, b, _congress, header_str):
    _id = congress_num * 100000 + types[_type] * 10000 + int(b['number'])
    API_response_bill = await connectASYNC(session, b['url'], header_str)
    API_response_actions = await connectASYNC(session, API_response_bill['bill']['actions']['url'], header_str)
    _member = await sync_to_async(Member.objects.get)(id=API_response_bill['bill']['sponsors'][0]['bioguideId'])
    _membership = await sync_to_async(Membership.objects.get)(congress=_congress, member=_member)
            
    _status = ('laws' in API_response_bill['bill']) and (len(API_response_bill['bill']['laws']) > 0)
    _bill = await sync_to_async(Bill.objects.get_or_create)(
        id = _id,
        title = b['title'],
        sponsor = _membership,
        status = _status,
        origin_date = API_response_bill['bill']['introducedDate'],
        latest_action = API_response_bill['bill']['latestAction']['actionDate']
        )

    _bill = _bill[0]
      
    senators = await sync_to_async(Membership.objects.filter)(congress=_congress, house=False)
    representatives = await sync_to_async(Membership.objects.filter)(congress=_congress, house=True)
    while API_response_actions is not None:
        for a in API_response_actions['actions']:
            if 'recordedVotes' in a:
                in_house = 0 if (a['recordedVotes'][0]['chamber'] != 'House') else 1
                vote_id = congress_num * 10000000 + in_house * 1000000 + int(a['recordedVotes'][0]['sessionNumber']) * 100000 + int(a['recordedVotes'][0]['rollNumber'])
                try:
                    vote_xml = await connectASYNC(vote_session, a['recordedVotes'][0]['url'], '', False)
                    vote_xml = vote_xml.content._buffer[0]
                    vote_xml = ET.XML(vote_xml)
                except aiohttp.ClientConnectionError as e:
                    print(f"Connection error: {e}")
                    return
                vote_dict = etree_to_dict(vote_xml)
                     
                vote_data = {
                    'id': vote_id,
                    'congress': _congress,
                    'house': in_house == 1,
                    'bill': _bill,
                    'dateTime': a['recordedVotes'][0]['date'],
                    'question': vote_dict['rollcall-vote']['vote-metadata']['vote-question'] if in_house == 1 else vote_dict['roll_call_vote']['question'],
                    'title': vote_dict['rollcall-vote']['vote-metadata']['vote-desc'] if in_house == 1 else vote_dict['roll_call_vote']['vote_title'],
                    'result': vote_dict['rollcall-vote']['vote-metadata']['vote-result'] if in_house == 1 else vote_dict['roll_call_vote']['vote_result']
                }
                _vote, created = await sync_to_async(Vote.objects.get_or_create)(**vote_data)
                if created:
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
                        'Nay': await sync_to_async(Membership.objects.none)(),
                        'No': await sync_to_async(Membership.objects.none)(),
                        'Not Voting': await sync_to_async(Membership.objects.none)(),
                        'Present': await sync_to_async(Membership.objects.none)()
                    }
                    keys = ['Yea', 'Nay', 'Not Voting', 'Present']
                    for m in members:
                        member = representatives.filter(member__id=m['legislator']['@name-id']) if in_house == 1 else senators.filter(
                            congress=_congress,
                            member__last_name__iexact=m['last_name'],
                            state=m['state']
                        )
                        q_sets[m['vote'] if in_house == 1 else m['vote_cast']] |= member
                    q_sets['Yea'] |= q_sets['Aye']
                    q_sets['Nay'] |= q_sets['No']
                    for key in keys:
                        await sync_to_async(member_votes[key].set)(q_sets[key])
                    print('Added Vote : ' + str(vote_id))
        if 'next' in API_response_actions['pagination']:
            API_response_actions = await connectASYNC(session, API_response_actions['pagination']['next'], header_str)
        else:
            API_response_actions = None
    return 1

## need to update this.. defunct
def addBill(congress_num, _type, _num):
    _id = congress_num * 100000 + types[_type] * 10000 + _num
    _congress = Congress.objects.get(congress_num__exact = congress_num)
    ## what do when type is h range...
    headers = {'api_key' : settings.CONGRESS_KEY, 'format' : 'json', 'limit' : '250'}

    API_response_bill = connect(settings.CONGRESS_DIR + "bill/" + str(congress_num) + "/" + _type + "/" + str(_num), headers).json()

    _member = Member.objects.get(id = API_response_bill['bill']['sponsors'][0]['bioguideId'])
    _membership = Membership.objects.get(congress = _congress, member = _member)
        
    _status = ('laws' in API_response_bill['bill']) and (len(API_response_bill['bill']['laws']) > 0)
    _bill = Bill.objects.get(
        id = _id)
  
    API_response_actions = connect(API_response_bill['bill']['actions']['url'], headers).json()
    senators = Membership.objects.filter(congress = _congress, house = False)
    representatives = Membership.objects.filter(congress = _congress, house = True)
    while API_response_actions != None:
        for a in API_response_actions['actions']:
            if 'recordedVotes' in a:
                in_house = 0 if (a['recordedVotes'][0]['chamber'] != 'House') else 1
                vote_id = congress_num * 10000000 + in_house * 1000000 + int(a['recordedVotes'][0]['sessionNumber']) * 100000 + int(a['recordedVotes'][0]['rollNumber'])
                if (True):
                    ##gets data from gov, in xml format...
                    ## what do when data is house vote???
                    vote_xml = connect(a['recordedVotes'][0]['url'], {}).content
                    vote_dict = xmltodict.parse(vote_xml)
                 
                    vote_data = {
                        'id': vote_id,
                        'congress': _congress,
                        'house': in_house == 1,
                        'bill': _bill,
                        'dateTime': a['recordedVotes'][0]['date'],
                        'question': vote_dict['rollcall-vote']['vote-metadata']['vote-question'] if in_house == 1 else vote_dict['roll_call_vote']['question'],
                        'title': vote_dict['rollcall-vote']['vote-metadata']['vote-desc'] if in_house == 1 else vote_dict['roll_call_vote']['vote_title'],
                        'result': vote_dict['rollcall-vote']['vote-metadata']['vote-result'] if in_house == 1 else vote_dict['roll_call_vote']['vote_result']
                    }
                    _vote, created = Vote.objects.get_or_create(**vote_data)
                    if True:
                        members = vote_dict['rollcall-vote']['vote-data']['recorded-vote'] if in_house == 1 else vote_dict['roll_call_vote']['members']['member']
                        member_votes = {
                            'Yea': _vote.yeas,
                            'Nay': _vote.nays,
                            'Not Voting': _vote.novt,
                            'Present': _vote.pres
                        }
                        q_sets = {
                            'Yea': Membership.objects.none(),
                            'Aye': Membership.objects.none(),
                            'Nay': Membership.objects.none(),
                            'No' : Membership.objects.none(),
                            'Not Voting': Membership.objects.none(),
                            'Present': Membership.objects.none()
                            }
                        keys = ['Yea' ,'Nay', 'Not Voting', 'Present']
                        for m in members:
                            member = representatives.filter(member__id=m['legislator']['@name-id']) if in_house == 1 else senators.filter(
                                congress=_congress,
                                member__last_name__iexact=m['last_name'],
                                state=m['state']
                            )
                            q_sets[m['vote'] if in_house == 1 else m['vote_cast']] |= member
                        q_sets['Yea'] |= q_sets['Aye']
                        q_sets['Nay'] |= q_sets['No']
                        for key in keys:
                            member_votes[key].set(q_sets[key])
                    print('Added Vote : ' + str(vote_id))
        if 'next' in API_response_actions['pagination']:
            API_response_actions = connect(API_response_actions['pagination']['next'], {'api_key' : settings.CONGRESS_KEY}).json()
        else : API_response_actions = None
    
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
    if _member.image_link != "empty": return API_response_member
    
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
                

    Member.objects.filter(id = member_id).update(
        full_name = API_response_member['member']['directOrderName'],
        first_name = API_response_member['member']['firstName'],
        last_name = API_response_member['member']['lastName'], 
        image_link = API_response_member['member']['depiction']['imageUrl'],
        office = office_addr,
        official_link = site,
        birth_year = API_response_member['member']['birthYear'],
        death_year = death_year,
        phone = phone_num
        )
    # need to somehow store history of legislation and party history and leadership
    return API_response_member;

def getBillsInRange(s_d, s_m, s_y, e_d, e_m, e_y):
    start_date = datetime(int(s_y), int(s_m), int(s_d))
    end_date = datetime(int(e_y), int(e_m), int(e_d))
    return Bill.objects.filter(origin_date__gte=start_date, origin_date__lte=end_date)

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

    ## can use status of bill object...
    if ('actionCode' in API_data[1]['actions'][0]) and (API_data[1]['actions'][0]['actionCode'] in ['E40000', '36000']) :
        context['bill_state_type'] = 'Became Public Law'
    else :
        context['bill_state_type'] = 'Still Just a Bill'
            
    context['actions_table'] = actionTable(API_data[1])
        
    # Handles sponsors and cosponsors
    list_start = '<li class="list-group-item"><a href="'
    member_link = '/member-query/results/?congress='
    bill_link = '/bill-query/results/bill/'
    q_2 = '&member='

    sponsor = API_data[0]['bill']['sponsors'][0]
    context['sponsor'] = '<a href="' + member_link  + congress_id + q_2 + sponsor['bioguideId']+ '">' + sponsor['fullName'] + '</a>'

    if (API_data[2] != ''):
        co_list = ''
        for c in API_data[2]['cosponsors']:
            co_list += list_start + member_link + congress_id + q_2 + c['bioguideId']+ '">' + c['fullName'] + '</a></li>'
        context['cosponsors'] = co_list
        
    if (API_data[3] != ''):
        related_bills = ''
        for b in API_data[3]['relatedBills'] : 
            related_bills += list_start + bill_link + str(b['congress']) + '/' + b['type'].lower() + '/' + str(b['number']) + '">' + b['type'] + '-' + str(b['number']) + '</a></li>'
        context['related_bills'] = related_bills
                  
    if (API_data[4] != ''):
        sub_list = ''
        for s in API_data[4]['subjects']['legislativeSubjects']:
            sub_list +=  '<li class="list-group-item">' + s['name'] + '</li>'
        context['subjects'] = sub_list
        context['policy_area'] = API_data[4]['subjects']['policyArea']['name']
            
    # currently jut gets first summary in list...
    if (API_data[5] != ''):
        context['summary'] = API_data[5]['summaries'][0]['text']
        
    #if ('textVersions' in API_response['bill']):
     #   API_committees= connect(API_response['bill']['textVersions']['url'], headers).json()
    
    return context

def voteHtml(vote):
    congress_id = vote.congress.__str__()
    q_2 = '&member='
       
    votes_list = [vote.nays, vote.yeas, vote.pres, vote.novt]
    list_color = {
        'Democratic': ' list-group-item-primary',
        'Republican': ' list-group-item-danger',
        'Independent': ' list-group-item-secondary',
        'Libertarian': ' list-group-item-warning',
        'Green': ' list-group-item-success'
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
        geojson_source = 'geojsons/cb_us_cd' + str(congress_id) + '_5m.geojson'
        geojson_load = 'scripts/loadCounty.js'
        values = [0] * mult
        text = [''] * mult
    else :
        mult = 50
        geojson_source = 'geojsons/cb_us_state_5m.geojson'
        geojson_load = 'scripts/loadState.js'
        values = [[0] * mult, [0] * mult, [0] * mult, [0] * mult]
        text = state_list

    geoids = [None] * mult
    #          0 : Nay, 1 : Yea, 2 : Present, 3 : No Vote
    for i in range(4):
        votes = votes_list[i].all()
        for membership in votes:
            html_lists[i] += '<li class="list-group-item' + list_color[membership.party] + '"><a href="/member-query/results/?congress=' 
            html_lists[i] += congress_id  + q_2 + membership.member.id+ '">' + membership.member.full_name + list_party[membership.party] + '</a></li>'
            if (membership.party not in partyCountsbyVote[i]) : partyCountsbyVote[i][membership.party] = 0
            partyCountsbyVote[i][membership.party] += 1
            if isHouseVote:
                text[j] = state_list[fips_to_count[membership.geoid[:2]]] + '-' + membership.geoid[2:]
                geoids[j] = membership.geoid
                values[j] = i
                j+=1
            else:
                indx = fips_to_count[membership.geoid]
                if indx == None : continue
                geoids[indx] = membership.geoid
                values[i][indx] += 1
                
        
    context = {'title': str(vote.id),
            'bill' : vote.bill.__str__(),
            'bill_title' : vote.bill.title,
            'bill_link' : '/bill-query/results/bill/' + congress_id  + '/' + vote.bill.getTypeURL() + '/' + vote.bill.getNumStr(),
            'vote_time' : str(vote.dateTime),
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
def actionTable(act_list):
    tableHTML = '<table class="table table-bordered table-small table-hover"><thead><tr><th>Action Date</th><th>Type</th><th>Text</th><th>Source</th></tr></thead><tbody>'
    for action in act_list['actions']:
        #check if action is ignorable
        if ('code' in action['sourceSystem'] and action['sourceSystem']['code'] == 9) and not (action['actionCode'] in ['1000', '10000', 'E30000', 'E40000']):
            continue
        tableHTML += '<tr><td>' + action['actionDate'] + '</td>';
        if ('recordedVotes' in action) :
            in_house = 0 if (action['recordedVotes'][0]['chamber'] != 'House') else 1
            vote_id = action['recordedVotes'][0]['congress'] * 10000000 + in_house * 1000000 + int(action['recordedVotes'][0]['sessionNumber']) * 100000 + int(action['recordedVotes'][0]['rollNumber'])
            tableHTML += '<td><a href="/bill-query/vote/' + str(vote_id) + '">' + 'Vote' + '</a></td>';    
        else : 
            tableHTML += '<td>' + action['type'] + '</td>';
        tableHTML += '<td>' + action['text'] + '</td><td>' + action['sourceSystem']['name'] + '</td></tr>';
    tableHTML += '</tbody></table>';
    return tableHTML

def billTable(bill_list):
    tableHTML = '<table class="table table-bordered table-small table-hover"><thead><tr><th>Origin Date</th><th>Bill ID</th><th>Title</th><th>Source</th></tr></thead><tbody>'
    for bill in bill_list:
        tableHTML += '<tr><td>' + str(bill.origin_date.month) + "/" + str(bill.origin_date.day) + "/" + str(bill.origin_date.year) + '</td>';
        tableHTML += '<td><a href="bill/' + str(bill.getCongress()) + '/' + bill.getTypeURL() + '/' + str(bill.getNum()) + '">' + bill.__str__() + '</a></td>';
        tableHTML += '<td>' + bill.title + '</td>';
        tableHTML += '<td>' + bill.getOrigin() + '</td></tr>';
    tableHTML += '</tbody></table>';
    return tableHTML

def voteTable(vote_list, bioguideID, congress_num):
    _congress = Congress.objects.get(congress_num__exact = congress_num)    
    _member = Member.objects.get(id__exact = bioguideID)
    tableHTML = '<table class="table table-bordered table-small table-hover"><thead><tr><th>Vote Date</th><th>Bill</th><th>Question</th><th>Vote</th></tr></thead><tbody>'
    colors = ['table-success', 'table-danger', 'table-secondary', '']
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
        tableHTML += '<tr class="' + colors[i] + '"><td>' + str(vote.dateTime) + '</td>';
        tableHTML += '<td><a href="/bill-query/results/bill/' + str(bill.getCongress()) + '/' + bill.getTypeURL() + '/' + str(bill.getNum()) + '">' + bill.__str__() + '</a></td>';
        tableHTML += '<td><a href="/bill-query/vote/' + str(vote.id) +  '">' + vote.question + '</a></td>';
        tableHTML += '<td>' + vote_type[i] + '</td></tr>';
    tableHTML += '</tbody></table>';
    return tableHTML
    
def partyList(party_history):
    party_list = ''
    for history in party_history:
        party_list += '<li class="list-group-item">' + history['partyName'] + ' (' + str(history['startYear']) + '-'
        if ('endYear' in history) : party_list += str(history['endYear'])
        else : party_list += 'Present'
        party_list += ')</li>'
    return party_list

def leadershipList(leaderships):
    leadership_list = ''
    for leadership in leaderships:
        leadership_list += '<li class="list-group-item">' + str(leadership['congress']) + getNumSuffix(leadership['congress'])
        leadership_list += ' Congress : ' + leadership['type']+ '</li>'
    return leadership_list
        
def termList(terms, bioguideID, congress_num):
    term_list = ''
    for term in reversed(terms):
        num = term['congress']
        link = '/member-query/results/?congress=' + str(num) + '&member=' + bioguideID
        district = ''
        if ('district' in term):
            district = ', '  + str(term['district']) + getNumSuffix(term['district']) + ' District'
            
        term_list += '<li class="list-group-item'
        if (term['congress'] == congress_num): term_list += ' list-group-item-primary'       
        term_list += '">'  + str(num) + getNumSuffix(num) + ' Congress : '
        term_list += '<a href="' + link + '">' + term['memberType'] + ' of ' + term['stateName'] + district + '</a>'
        term_list += '(' + str(term['startYear']) + '-'
        if ('endYear' in term) : term_list += str(term['endYear'])
        else : term_list += 'Present'
        term_list += ')</a></li>'
    return term_list
    
    