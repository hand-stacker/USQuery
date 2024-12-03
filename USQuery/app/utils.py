import requests, json, time
from USQuery import settings
from requests.exceptions import HTTPError
from SenateQuery.models import Member, Congress, Membership

def connect(fullpath, host, newSearch = True):
    if (host == "Congress"):
        headers = {'api_key' : settings.CONGRESS_KEY};
        if (newSearch):
            headers['format'] = 'json'
            headers['curerentMember'] = 'false'
            headers['offset'] = '0'
            headers['limit'] = '250'
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
        return response.json()

def getDirectOrderName(reverseName):
    try:
        commaIndx = reverseName.index(',')
    except ValueError:
            return ValueError
    return reverseName[commaIndx + 1: ] + " " + reverseName[:commaIndx]

def addMembersCongressAPILazy(congress_num):
    API_cong = connect(settings.CONGRESS_DIR + '/congress/' + str(congress_num), 'Congress')
    
    start_rep = API_cong['congress']['sessions'][0]['startDate']
    end_rep = API_cong['congress']['sessions'][2]['endDate']
    start_sen = API_cong['congress']['sessions'][1]['startDate']
    end_sen = API_cong['congress']['sessions'][3]['endDate']
    API_response = connect(settings.CONGRESS_DIR + "/member/congress/" + str(congress_num), "Congress")
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
            full_name = getDirectOrderName(member['name'])
            _set_member = Member.objects.filter(id = _id)
            if (_set_member.exists()):
                _member = _set_member[0]
            else :
                _member = Member.objects.get_or_create(id = _id, 
                full_name = full_name,
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
            API_response = connect(API_response['pagination']['next'], "Congress", False)
        else : API_response = None
    return

def findIndexOfRoleByChamberAndCongress(roles, congress_num, chamber):
    for i in range(len(roles)):
        if (roles[i]['congress'] == str(congress_num)) & (roles[i]['chamber'] == chamber): 
            return i
    return -1   
        
                    #defunct, fix later
def updateMember(congress_num, member_id): 
    _congress = Congress.objects.get(congress_num__exact = congress_num)    
    _member = Member.objects.get(id__exact = member_id)
    """
    if _member.image_link != 'empty':
        return
        """
    Membership.objects.get(
                            congress = _congress,
                            member = _member
                            )
    API_response_member = connect(_member.api_url, "Congress")
    office_addr = None
    phone_num = None
    death_year = None
    site = None
    
    if ('deathYear' in API_response_member['member']) :
        death_year = API_response_member['member']['deathYear']
        
    if (API_response_member['member']['currentMember']) :
        site = API_response_member['member']['officialWebsiteUrl']
        office_addr = API_response_member['member']['addressInformation']['officeAddress'] + ', ' + API_response_member['member']['addressInformation']['city'] + " " + API_response_member['member']['addressInformation']['district'] + ", " + str(API_response_member['member']['addressInformation']['zipCode'])
        phone_num = API_response_member['member']['addressInformation']['phoneNumber']

    Member.objects.filter(id = member_id).update(
        image_link = API_response_member['member']['depiction']['imageUrl'],
        office = office_addr,
        official_link = site,
        birth_year = API_response_member['member']['birthYear'],
        death_year = death_year,
        phone = phone_num
       
        )
    # need to somehow store history of legislation and party history and leadership
    return API_response_member;