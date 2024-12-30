import requests, json, time
from USQuery import settings
from requests.exceptions import HTTPError
from SenateQuery.models import Member, Congress, Membership
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
        return response
    
def getFirstAndLastName(reverseName):
    try:
        commaIndx = reverseName.index(',')
    except ValueError:
            return ValueError
    return [reverseName[commaIndx + 1: ], reverseName[:commaIndx]]


def addMembersCongressAPILazy(congress_num):
    headers = {'api_key' : settings.CONGRESS_KEY, 'format' : 'json'}
    const_headers = headers
    headers['curerentMember'] = 'false'
    headers['offset'] = '0'
    headers['limit'] = '250'
    
    API_cong = connect(settings.CONGRESS_DIR + '/congress/' + str(congress_num), const_headers).json()
    
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
        if 'next' in API_response['pagination']:
            API_response = connect(API_response['pagination']['next'], const_headers).json()
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
    headers = {'api_key' : settings.CONGRESS_KEY, 'format' : 'json'}
    headers['fromDateTime'] = s_y + "-" + s_m + "-" + s_d + "T00:00:00Z"
    headers['toDateTime'] = e_y + "-" + e_m + "-" + e_d + "T00:00:00Z"
    headers['limit'] = '25'
    headers['sort'] = "updateDate"
    API_response = connect(settings.CONGRESS_DIR + "bill?" , headers).json()
    return API_response

def convertBillData(data):
    ret = {}
    for i in range(len(data)):
        ret[str(i)] = data[i];
    return ret

def getBill(API_url):
    headers = {'api_key' : settings.CONGRESS_KEY, 'format' : 'json'}
    API_response = connect(settings.CONGRESS_DIR + "bill?" , headers).json()
    return API_response
    