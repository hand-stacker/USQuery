from datetime import datetime
import requests, json, time, xmltodict
from USQuery import settings
from requests.exceptions import HTTPError
from SenateQuery.models import Member, Congress, Membership
from BillQuery.models import Bill, Vote, ChoiceVote, Choice

def modifyCountyGeoJSON(congress_id):
    read_url = 'BillQuery/static/geojsons/cb_us_cd' + str(congress_id) + '_5m.geojson'
    write_url = 'BillQuery/static/geojsons/cb_us_cd' + str(congress_id) + '_5m.geojson'
    modify(read_url, write_url)

def modifyStateGeoJSON():
    read_url = 'BillQuery/static/geojsons/cb_us_state_5m.geojson'
    write_url = 'BillQuery/static/geojsons/cb_us_state_5m.geojson'
    modify(read_url, write_url)

def modify(read_url, write_url):
    with open(read_url) as json_file:
        data = json.load(json_file)
        for i in range(len(data['features'])) : 
            data['features'][i]['id'] = data['features'][i]['properties']['GEOID']
        with open(write_url, 'w') as write_file:
            json.dump(data, write_file, indent=1)