from datetime import datetime
from token import COMMA
import requests, json, time, xmltodict
from USQuery import settings
from requests.exceptions import HTTPError
from SenateQuery.models import Member, Congress, Membership
from BillQuery.models import Bill, Vote, ChoiceVote, Choice

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
              }

def connect(fullpath, headers):
    try:
        response = requests.get(fullpath, headers, timeout=20)
        response.raise_for_status()
    except HTTPError as http_err:
        print(f'HTTP ERROR : {http_err}')
    except Exception as err:
        print(f'MISC ERROR : {err}')
    except TimeoutError:
        print("TIMEOUT ERROR")
    else:
        print('Connected to ' + fullpath)
        return response
    
## last name is correct, need to fix first name
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


def addMembersCongressAPILazy(congress_num):
    headers = {'api_key' : settings.CONGRESS_KEY, 'format' : 'json'}
    headers['curerentMember'] = 'false'
    headers['offset'] = '0'
    headers['limit'] = '250'
    
    API_cong = connect(settings.CONGRESS_DIR + '/congress/' + str(congress_num), headers).json()
    
    start_rep = API_cong['congress']['sessions'][0]['startDate']
    end_rep = API_cong['congress']['sessions'][2]['endDate']
    start_sen = API_cong['congress']['sessions'][1]['startDate']
    end_sen = API_cong['congress']['sessions'][3]['endDate']
    
    API_response = connect(settings.CONGRESS_DIR + "/member/congress/" + str(congress_num), headers).json()
    congress = Congress.objects.get_or_create(congress_num = congress_num)[0]
    
    while (API_response != None):
        for member in API_response['members']:
            _id=member['bioguideId']
            if (member['district'] == None):
                district = None
                role = "Senate"
            else :
                district = member['district']
                role = "House of Representatives"
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
                _member = Member.objects.get_or_create(id = _id, 
                full_name = full_name,
                first_name = name[0],
                last_name = name[1],
                image_link = "empty",
                api_url = member['url'])[0] 
                    
            Membership.objects.get_or_create(
                        congress = congress,
                        member = _member,
                        district_num = district,
                        chamber = role,
                        state = member['state'],
                        party = member['partyName'],
                        start_date = start_sen if (role == "Senate") else start_rep,
                        end_date = end_sen if (role == "Senate") else end_rep,
                        )
            print("added member " + _id)
        if 'next' in API_response['pagination']:
            API_response = connect(API_response['pagination']['next'], {'api_key' : settings.CONGRESS_KEY}).json()
        else : API_response = None
    return

def findIndexOfRoleByChamberAndCongress(roles, congress_num, chamber):
    for i in range(len(roles)):
        if (roles[i]['congress'] == str(congress_num)) & (roles[i]['chamber'] == chamber): 
            return i
    return -1   
        
                    
def updateMember(congress_num, member_id): 
    _congress = Congress.objects.get(congress_num__exact = congress_num)    
    _member = Member.objects.get(id__exact = member_id)
    Membership.objects.get(
                            congress = _congress,
                            member = _member
                            )
    if _member.image_link != "empty": return
    
    API_response_member = connect(_member.api_url, {'api_key' : settings.CONGRESS_KEY, 'format' : 'json'}).json()
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

def getBillBlob(bill_list):
    tableHTML = '<table class="table table-bordered table-small table-hover"><tr><thead><th>Origin Date</th><th>Bill ID</th><th>Title</th><th>Source</tr></thead>'
    for bill in bill_list:
        tableHTML += '<tr>';
        tableHTML += '<td>' + str(bill.origin_date.month) + "/" + str(bill.origin_date.day) + "/" + str(bill.origin_date.year) + '</td>';
        tableHTML += '<td>''<a href="bill/' + str(bill.getCongress()) + '/' + bill.getTypeURL() + '/' + str(bill.getNum()) + '">' + bill.__str__() + '</a></td>';
        tableHTML += '<td>' + bill.title + '</td>';
        tableHTML += '<td>' + bill.getOrigin() + '</td>';
        tableHTML += '</tr>';

    tableHTML += '</table>';
    return tableHTML

def convertBillData(data):
    ret = {}
    for i in range(len(data)):
        ret[str(i)] = data[i];
    return ret

## mega function that creates bills, and from bills creates votes
## ideally do not add more than 100 bills per call!
def addBills(congress_num = 116, _type='s', limit = 100, offset = 0):
    types = {
            "s" : 0,
            "sres" : 1,
            "sjres" : 2,
            "sconres" : 3,
            "hr" : 4,
            "hres" : 5,
            "hjres" : 6,
            "hconres" : 7}
    base_id = congress_num * 100000 + types[_type] * 10000
    _congress = Congress.objects.get(congress_num__exact = congress_num)
    in_house = 0 if (types[_type] <= 3) else 1
    ## what do when type is h range...
    headers = {'api_key' : settings.CONGRESS_KEY, 'format' : 'json', 'limit' : str(limit), 'offset' : str(offset)}
    API_response = connect(settings.CONGRESS_DIR + "bill/" + str(congress_num) + "/" + _type + "?", headers).json()
    for b in API_response['bills']:
        _id = base_id + int(b['number'])
        API_response_bill = connect(b['url'], headers).json()
        
        _bill = Bill.objects.get_or_create(id = _id, title = b['title'], origin_date = API_response_bill['bill']['introducedDate'], latest_action = API_response_bill['bill']['latestAction']['actionDate'])[0]
  
        API_response_actions = connect(API_response_bill['bill']['actions']['url'], {'api_key' : settings.CONGRESS_KEY}).json()
        
        while API_response_actions != None:
            for a in API_response_actions['actions']:
                if 'recordedVotes' in a:
                    ##gets data from gov, in xml format...
                    ## what do when data is house vote???
                    vote_xml = connect(a['recordedVotes'][0]['url'], {}).content
                    vote_dict = xmltodict.parse(vote_xml)
                    vote_id = congress_num * 10000000 + in_house * 1000000 + int(a['recordedVotes'][0]['sessionNumber']) * 100000 + int(a['recordedVotes'][0]['rollNumber'])
                    if (Vote.objects.filter(id=vote_id).first() != None): break
                    if (a['recordedVotes'][0]['chamber'] == 'House'):
                        _vote = Vote.objects.get_or_create(id = vote_id,
                                                            congress = _congress,
                                                            bill = _bill,
                                                            dateTime = a['recordedVotes'][0]['date'],
                                                            question = vote_dict['rollcall-vote']['vote-metadata']['vote-question'],
                                                            title = vote_dict['rollcall-vote']['vote-metadata']['vote-desc'],
                                                            result = vote_dict['rollcall-vote']['vote-metadata']['vote-result']
                                                            )[0]
                        _vote.save()
                        for m in vote_dict['rollcall-vote']['vote-data']['recorded-vote']:
                            member = Membership.objects.filter(member__id= m['legislator']['@name-id'], congress = _congress)[0]
                            if m['vote'] == 'Yea' :
                                _vote.yeas.add(member)
                            elif m['vote'] == 'Nay':
                                _vote.nays.add(member)
                            elif m['vote'] == 'Not Voting':
                                _vote.novt.add(member)
                            else :
                                _vote.pres.add(member)
                    else :
                        _vote = Vote.objects.get_or_create(id = vote_id,
                                                            congress = _congress,
                                                            bill = _bill,
                                                            dateTime = a['recordedVotes'][0]['date'],
                                                            question = vote_dict['roll_call_vote']['question'],
                                                            title = vote_dict['roll_call_vote']['vote_title'],
                                                            result = vote_dict['roll_call_vote']['vote_result']
                                                            )[0]
                        _vote.save()
                        for m in vote_dict['roll_call_vote']['members']['member']:
                            member = Membership.objects.filter(congress = _congress,
                                                               member__last_name__iexact = m['last_name'],
                                                               chamber = 'Senate',
                                                               state = state_dict[m['state']])[0]
                            if m['vote_cast'] == 'Yea' :
                                _vote.yeas.add(member)
                            elif m['vote_cast'] == 'Nay':
                                _vote.nays.add(member)
                            elif m['vote_cast'] == 'Not Voting':
                                _vote.novt.add(member)
                            else :
                                _vote.pres.add(member)
                    print('Added Vote : '  + str(vote_id))
            if 'next' in API_response_actions['pagination']:
                API_response_actions = connect(API_response_actions['pagination']['next'], {'api_key' : settings.CONGRESS_KEY}).json()
            else : API_response_actions = None
            
def BillHtml(congress_id, bill_type, num):
    apiURL = settings.CONGRESS_DIR + "bill/" + congress_id + "/" + bill_type + "/" + num
    headers = {'api_key' : settings.CONGRESS_KEY, 'format' : 'json', 'limit' : '250'}
    API_response = connect(apiURL, headers).json()
    
    context = {'title':"CONGRESS: " + congress_id + ", " + bill_type.upper() + "-" + num,
            'year' : datetime.now().year,
            'bill' : bill_type.upper() + "-" + num,
            }
    
    # actions and amendments need to be tablified

    if ('actions' in API_response['bill']):
        API_actions = connect(API_response['bill']['actions']['url'], headers).json()
        if API_actions['actions'][0]['actionCode'] in ['E40000', '36000'] :
            context['bill_state_type'] = 'Became Public Law'
        else :
            context['bill_state_type'] = 'Waiting...'
            
        context['actions_table'] = makeActionTable(API_actions)
       
    #if ('amendments' in API_response['bill']):
    #    API_committees= connect(API_response['bill']['committees']['amendments'], headers).json()
    #    context['amendments_table'] = makeAmendmentTable(API_committees)
        
    # Do we want committee data??
    # if ('committiees' in API_response['bill']):
        # API_committees= connect(API_response['bill']['committees']['url'], headers).json()
        
    # Handles sponsors and cosponsors
    context['sponsor'] = '<a href="' +settings.BASE_DIR + '">' + API_response['bill']['sponsors'][0]['fullName'] + '</a>'
    
    if ('cosponsors' in API_response['bill']):
        co_list = []
        API_cosponsors= connect(API_response['bill']['cosponsors']['url'], headers).json()
        for c in API_cosponsors['cosponsors']:
            temp = '<a href="' +settings.BASE_DIR + "/members" + '">' + c['fullName'] + '</a>'
            co_list.append(temp)
        context['cosponsors'] = co_list
        
    if ('relatedBills' in API_response['bill']):
        API_related= connect(API_response['bill']['relatedBills']['url'], headers).json()
        re_list = []
        for b in API_related['relatedBills'] : 
            temp = '<a href="bill/' + str(b['congress']) + '/' + b['type'].lower() + '/' + str(b['number']) + '">' + c['fullName'] + '</a>'
            re_list.append(temp)
        
    if ('subjects' in API_response['bill']):
        API_subjects= connect(API_response['bill']['subjects']['url'], headers).json()
        sub_list = []
        for s in API_subjects['subjects']['legislativeSubjects']:
            sub_list.append(s['name'])
        context['subjects'] = sub_list
        context['policy_area'] = API_subjects['subjects']['policyArea']['name']
            
    # currently jut gets first summary in list...
    if ('summaries' in API_response['bill']):
        API_summaries= connect(API_response['bill']['summaries']['url'], headers).json()
        context['summary'] = API_summaries['summaries'][0]['text']
        
    #if ('textVersions' in API_response['bill']):
     #   API_committees= connect(API_response['bill']['textVersions']['url'], headers).json()
    
    return context

# type column will have links if its a vote
def makeActionTable(act_list):
    tableHTML = '<table class="table table-bordered table-small table-hover"><tr><thead><th>Action Date</th><th>Type</th><th>Text</th><th>Source</tr></thead>'
    for action in act_list['actions']:
        #check if action is ignorable
        if ('code' in action['sourceSystem'] and action['sourceSystem']['code'] == 9) and not (action['actionCode'] in ['1000', '10000']):
            continue
        tableHTML += '<tr>';
        tableHTML += '<td>' + action['actionDate'] + '</td>';
        if ('recordedVotes' in action) :
            tableHTML += '<td><a href="vote/' + str(action['recordedVote']['congress']) + '/' + str(action['recordedVote']['sessionNumber']) + '/' + str(action['recordedVote']['rollNumber']) + '">' + 'Vote' + '</a></td>';    
        else : 
            tableHTML += '<td>' + action['type'] + '</td>';
        tableHTML += '<td>' + action['text'] + '</td>';
        tableHTML += '<td>' + action['sourceSystem']['name'] + '</td>';
        tableHTML += '</tr>';

    tableHTML += '</table>';
    return tableHTML

def makeAmendmentTable(amend_list):
    tableHTML = '<table class="table table-bordered table-small table-hover"><tr><thead><th>Action Date</th><th>Type</th><th>Text</th><th>Source</tr></thead>'
    tableHTML += '</table>';
    return tableHTML
        
        
    
    