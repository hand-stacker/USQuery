from SenateQuery import congconnect as conn
from SenateQuery.models import Senator
from datetime import datetime

# get current congress number
congress_num = "117"

## Operation assumes each call only has an incremental congress num
API_response = conn.connect(congress_num + "/senate/members.json")
API_response = None
if API_response != None:
    for member in API_response['members']:
        match = Senator.objects.filter(id=member['id'])
        if match:
            match.update(
                first_name = member['first_name'],
                middle_name = member['middle_name'],
                last_name = member['last_name'],
                suffix = member['suffix'],
                gender = member['gender'],
                birth_date = member['date_of_birth'],
                url = member['url'],
                twitter_user = member['twitter_account'],
                facebook_user = member['facebook_account'],
                youtube_user = member['youtube_account'],
                party = member['party'],
                state = member['state'])
        else:
            Senator.objects.get_or_create(
                id = member['id'],
                first_name = member['first_name'],
                middle_name = member['middle_name'],
                last_name = member['last_name'],
                suffix = member['suffix'],
                gender = member['gender'],
                birth_date = member['date_of_birth'],
                url = member['url'],
                twitter_user = member['twitter_account'],
                facebook_user = member['facebook_account'],
                youtube_user = member['youtube_account'],
                party = member['party'],
                state = member['state'])
        

