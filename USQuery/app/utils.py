import requests, json, time
from USQuery import settings
from requests.exceptions import HTTPError
from SenateQuery.models import Member, Congress, Senatorship, Representativeship

def connect(fullpath, host):
    try:
        if (host == 'ProPublica'):
            response = requests.get(fullpath, headers={'X-API-Key': settings.PROPUBLICA_KEY}, timeout=20)
        else:
            response = requests.get(fullpath + '?api_key=' + settings.CONGRESS_KEY, timeout=20)
        response.raise_for_status()
    except HTTPError as http_err:
        print(f'HTTP ERROR : {http_err}')
    except Exception as err:
        print(f'MISC ERROR : {err}')
    except TimeoutError:
        print("TIMEOUT ERROR")
    else:
        if (host == 'ProPublica'):
            return response.json()['results']
        else:
            return response.json()
    
def makeFullName(first_name, last_name, middle_name=None, suffix=None, short_title=None):
    full_name = ""
    if (short_title is not None):
        full_name += short_title + " "
    full_name += first_name
    if (middle_name is not None):
        full_name += " " + middle_name 
    full_name += " " + last_name
    if (suffix is not None):
        full_name += " " + suffix
    return full_name

def findIndexOfRoleByChamberAndCongress(roles, congress_num, chamber):
    for i in range(len(roles)):
        if (roles[i]['congress'] == str(congress_num)) & (roles[i]['chamber'] == chamber): 
            return i
    return -1   
        
# must give congress num and who you're adding or else adds senators from 80th congress
def addMemberByCongressLazy(congress_num = 80, adding = "senate"):
        API_response = connect(settings.PROPUBLICA_DIR + str(congress_num) + "/" + adding + "/members.json", "ProPublica")
        API_response = API_response[0]
        if API_response != None:
            congress = Congress.objects.get_or_create(congress_num = congress_num)[0]
            for member in API_response['members']:
                _id=member['id']
                if (adding == "senate"):
                    _set = congress.senators.filter(id = _id)
                    if _set.exists() and Senatorship.objects.filter(congress = congress, senator = _set[0]).exists():
                        continue 
                else:
                    _set = congress.representatives.filter(id = _id)
                    if _set.exists() and Representativeship.objects.filter(congress = congress, representative = _set[0]).exists():
                        continue 
                full_name = makeFullName(
                        member['first_name'],
                        member['last_name'],
                        member['middle_name'],
                        member['suffix']
                        )
                _set_member = Member.objects.filter(id = _id)
                if (_set_member.exists()):
                    _member = _set_member[0]
                else:
                    _member = Member.objects.get_or_create(id = _id, 
                        full_name = full_name,
                        image_link = "empty",
                        url = member['url'],
                        twitter = member['twitter_account'],
                        facebook = member['facebook_account'],
                        youtube = member['youtube_account'],
                        office = member['office'],
                        phone = member['phone'],
                        votesmart_id = member['votesmart_id']
                                                            )[0]
                if (adding == "senate"):
                    Senatorship.objects.get_or_create(senator = _member,
                                                 congress = congress,
                                                 state = member['state'],
                                                 party = member['party'],
                                                 short_title = member['short_title'],
                                                 long_title = member['title'],
                                                 start_date = "0",
                                                 end_date = "0",
                                                 total_votes = member['total_votes'],
                                                 missed_votes = member['missed_votes'],
                                                 total_present = member['total_present'],
                                                 party_votes_pct = 0.0,
                                                 nonparty_votes_pct = 0.0,
                                                 missed_votes_pct = 0.0,
                                                 cook_pvi = member['cook_pvi'],
                                                 )
                else:
                    Representativeship.objects.get_or_create(representative = _member,
                                                 congress = congress,
                                                 state = member['state'],
                                                 party = member['party'],
                                                 short_title = member['short_title'],
                                                 long_title = member['title'],
                                                 start_date = "0",
                                                 end_date = "0",
                                                 total_votes = member['total_votes'],
                                                 missed_votes = member['missed_votes'],
                                                 total_present = member['total_present'],
                                                 party_votes_pct = 0.0,
                                                 nonparty_votes_pct = 0.0,
                                                 missed_votes_pct = 0.0,
                                                 cook_pvi = member['cook_pvi'],
                                                 )
                    
def updateMembership(congress_num, role, member_id):
    member_response = connect(settings.PROPUBLICA_DIR + "members/" + member_id + ".json", "ProPublica")
    member_response = member_response[0]
    US_response = connect(settings.CONGRESS_DIR + "member/" + member_id, "Congress")
    if (role == "senate"):
        index = findIndexOfRoleByChamberAndCongress(member_response['roles'], congress_num, 'Senate')
    else:
        index = findIndexOfRoleByChamberAndCongress(member_response['roles'], congress_num, 'House')
    if index == -1:
        print("FATAL DATABASE ERROR")
    _member = Member.objects.get(id__exact = member_id)
    if (role == "senate"):
        Senatorship.objects.filter(senator = _member, congress = congress_num).update(
            start_date = member_response['roles'][index]['start_date'],
            end_date = member_response['roles'][index]['end_date'],
            total_votes = member_response['roles'][index]['total_votes'],
            missed_votes = member_response['roles'][index]['missed_votes'],
            total_present = member_response['roles'][index]['total_present'],
            party_votes_pct = member_response['roles'][index]['votes_with_party_pct'],
            nonparty_votes_pct = member_response['roles'][index]['votes_against_party_pct'],
            missed_votes_pct = member_response['roles'][index]['missed_votes_pct'],
            cook_pvi = member_response['roles'][index]['cook_pvi']
            )
    else:
        Representativeship.objects.filter(representative = _member, congress = congress_num).update(
            start_date = member_response['roles'][index]['start_date'],
            end_date = member_response['roles'][index]['end_date'],
            total_votes = member_response['roles'][index]['total_votes'],
            missed_votes = member_response['roles'][index]['missed_votes'],
            total_present = member_response['roles'][index]['total_present'],
            party_votes_pct = member_response['roles'][index]['votes_with_party_pct'],
            nonparty_votes_pct = member_response['roles'][index]['votes_against_party_pct'],
            missed_votes_pct = member_response['roles'][index]['missed_votes_pct'],
            cook_pvi = member_response['roles'][index]['cook_pvi']
            )
    Member.objects.filter(id = member_id).update(image_link = US_response['member']['depiction']['imageUrl'])