from app import utils
from SenateQuery import congconnect as conn
from SenateQuery.models import Senator, Senatorship, Congress

def add(congress_num=80):
    API_response = conn.connect(str(congress_num) + "/senate/members.json")[0]
    if API_response != None:
        congress = Congress.objects.get_or_create(congress_num = congress_num)[0]
        for member in API_response['members']:
            senator = Senator.objects.get_or_create(id=member['id'], full_name = utils.makeFullName(
                member['first_name'],
                member['last_name'],
                member['middle_name'],
                member['suffix']))[0]
            Senatorship.objects.get_or_create(senator = senator, congress = congress, state = member['state'])