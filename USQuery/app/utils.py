import requests, json
from USQuery import settings
from requests.exceptions import HTTPError
from SenateQuery.models import Senator, Senatorship, Congress

def connect(fullpath, host):
    try:
        if (host == 'ProPublica'):
            response = requests.get(fullpath, headers={'X-API-Key': settings.PROPUBLICA_KEY}, timeout=200)
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

def addSenatorsByCongress(congress_num=80):
    API_response = connect(settings.PROPUBLICA_DIR + str(congress_num) + "/senate/members.json", "ProPublica")
    API_response = API_response[0]
    if API_response != None:
        congress = Congress.objects.get_or_create(congress_num = congress_num)[0]
        for member in API_response['members']:
            _id=member['id']
            senator_response = connect(member['api_uri'], "ProPublica")
            senator_response = senator_response[0]
            US_response = connect(settings.CONGRESS_DIR + "member/" + _id, "Congress")
            index = findIndexOfRoleByChamberAndCongress(senator_response['roles'], congress_num, 'Senate')
            if index == -1:
                print("FATAL DATABASE ERROR")
            full_name = makeFullName(
                    member['first_name'],
                    member['last_name'],
                    member['middle_name'],
                    member['suffix']
                    )
            senator = Senator.objects.get_or_create(id = _id, 
                full_name = full_name,
                image_link = US_response['member']['depiction']['imageUrl'],
                url = member['url'],
                twitter = member['twitter_account'],
                facebook = member['facebook_account'],
                youtube = member['youtube_account'],
                office = member['office'],
                phone = member['phone'],
                votesmart_id = member['votesmart_id']
                                                    )[0]
            Senatorship.objects.get_or_create(senator = senator,
                                             congress = congress,
                                             state = member['state'],
                                             party = member['party'],
                                             short_title = member['short_title'],
                                             long_title = member['title'],
                                             start_date = senator_response['roles'][index]['start_date'],
                                             end_date = senator_response['roles'][index]['end_date'],
                                             total_votes = senator_response['roles'][index]['total_votes'],
                                             missed_votes = senator_response['roles'][index]['missed_votes'],
                                             total_present = senator_response['roles'][index]['total_present'],
                                             party_votes_pct = senator_response['roles'][index]['votes_with_party_pct'],
                                             nonparty_votes_pct = senator_response['roles'][index]['votes_against_party_pct'],
                                             missed_votes_pct = senator_response['roles'][index]['missed_votes_pct'],
                                             cook_pvi = senator_response['roles'][index]['cook_pvi'],
                                             )