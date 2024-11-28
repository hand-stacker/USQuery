from math import e
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
            headers['limit'] = '107'
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
    
def addMembersCongressAPILazy(congress_num):
    API_response = connect(settings.CONGRESS_DIR + "/member/congress/" + str(congress_num), "Congress")
    congress = Congress.objects.get_or_create(congress_num = congress_num)[0]
    if API_response != None:
        count = 0;
        while (count < 5):
            for member in API_response['members']:
                ## have to find a way to find role from data...
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
                full_name = member['name']
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
                            start_date = "empty",
                            end_date = "empty",
                            )
            API_response = connect(API_response['pagination']['next'], "Congress", False)
            count += 1 
    return

def findIndexOfRoleByChamberAndCongress(roles, congress_num, chamber):
    for i in range(len(roles)):
        if (roles[i]['congress'] == str(congress_num)) & (roles[i]['chamber'] == chamber): 
            return i
    return -1   
        
                    #defunct, fix later
def updateMembership(congress_num, role, member_id): 
    _congress = Congress.objects.get(id__exact = congress_num)    
    _member = Member.objects.get(id__exact = member_id)
    if _member['api_url'] != 'empty':
        return
    Membership.objects.get(
                            congress = _congress,
                            member = _member
                            )
    API_response_congress = connect(settings.CONGRESS_DIR + "/congress/" + str(congress_num), "Congress")
    if (API_response_congress == None) : return
    endyear = int(API_response_congress['endYear'])
    
    member_response = connect(settings.PROPUBLICA_DIR + "members/" + member_id + ".json?offset=0", "ProPublica")
    member_response = member_response[0]
    US_response = connect(settings.CONGRESS_DIR + "member/" + member_id, "Congress")
    if (role == "senate"):
        index = findIndexOfRoleByChamberAndCongress(member_response['roles'], congress_num, 'Senate')
    else:
        index = findIndexOfRoleByChamberAndCongress(member_response['roles'], congress_num, 'House')
    if index == -1:
        print("FATAL DATABASE ERROR")
    
    if (role == "Senate"):
        Membership.objects.filter(senator = _member, congress = congress_num).update(
            start_date = member_response['roles'][index]['start_date'],
            end_date = member_response['roles'][index]['end_date']
            )
    else:
        Membership.objects.filter(representative = _member, congress = congress_num).update(
            start_date = member_response['roles'][index]['start_date'],
            end_date = member_response['roles'][index]['end_date']
            )
    Member.objects.filter(id = member_id).update(image_link = US_response['member']['depiction']['imageUrl'])