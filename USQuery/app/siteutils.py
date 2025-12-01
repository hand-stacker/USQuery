import asyncio, aiohttp, json
import numpy as np
import pandas as pd
import tensorflow as tf
import datetime
import secretss
import ast
import re
from scipy.stats import binom
from bs4 import BeautifulSoup
from google.genai import types
from google import genai
from django.db.models import Q
from USQuery import settings
from app import utils
from SenateQuery.models import Membership
from BillQuery.models import BillPrediction, BinaryProbability, Bill

types_list = ['s','sres','sjres','sconres','hr','hres','hjres','hconres']
pattern = re.compile(r'\s{2,}')
prompt = secretss.prompt
column_list = secretss.column_list
column_dict = secretss.column_dict
model = 'gemini-2.0-flash'

# GeoJSON modification function
# used once to modify GeoJSON for site, use when adding a new GeoJSON map of counties/states
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


# Model N1 functions
#
#
# returns features dict, or None if possible token count exceeds limit
async def gatherFeatures(bill_id):
    header_str = 'api_key=' + settings.CONGRESS_KEY + '&format=json&limit=250'
    session = aiohttp.ClientSession()
    client = genai.Client(api_key= settings.GEMINI_KEY)
    generate_content_config = types.GenerateContentConfig(response_mime_type='text/plain')
    mult = 1 if bill_id < 99_999_999 else 10
    congress_num = bill_id // (100000 * mult)
    type_enum = (bill_id // (10000 * mult)) % 10
    bill_type = types_list[type_enum]
    bill_num = bill_id % (10000 * mult)
    fullpath = settings.CONGRESS_DIR + 'bill/' + str(congress_num) + '/' + bill_type + '/' + str(bill_num)
    blob = await utils.run_concurrent_connect(session, [fullpath + '/text?', fullpath + '/subjects?'], header_str)
    subjects = blob[1]
    texts = blob[0]
    if len(texts['textVersions']) == 0 or len(subjects['subjects']['legislativeSubjects']) == 0: return None
    subj_litr = '['
    for subject in subjects['subjects']['legislativeSubjects']:
        subj_litr += '"' + subject['name'] + '",'
    subj_litr += ']'
    indx = -1
    date_max = datetime.datetime(1,1,1,1,1,1)
    for j in range(len(texts['textVersions'])):
        date_str = texts['textVersions'][j]['date']
        if date_str == None: continue
        curr_date = datetime.datetime(
            int(date_str[0:4]),
            int(date_str[5:7]),
            int(date_str[8:10]),
            int(date_str[11:13]),
            int(date_str[14:16]),
            int(date_str[17:19])
            )
        if curr_date > date_max:
            date_max = curr_date
            indx = j
    txt_html = await utils.connectASYNC(session, texts['textVersions'][indx]['formats'][0]['url'], '', False)
    if txt_html == None : return None
    soup = BeautifulSoup(txt_html)
    version_text = soup.get_text()
    version_text = version_text.replace('\n','').replace('_','')
    version_text = re.sub(pattern, ' ', version_text)
    ctns=[version_text,subj_litr, prompt]
    token_count = client.models.count_tokens(model=model, contents=ctns)
    if token_count.total_tokens > 1_000_000 : return None
    response = await client.aio.models.generate_content(
        model = model,
        contents = ctns,
        config = generate_content_config
        )
    response = response.text
    response = response.removeprefix('```python')
    response = response.removesuffix('```')
    response = response.removesuffix('```\n')
    try :
        d = ast.literal_eval(response)
    except:
        return None
    for key in list(d.keys()):
        if key not in column_dict:
            d.pop(key)
    await session.close()
    return d

# returns -1 if any errors occured, 1 if creation was successfull
def createPredictions(bill_id):
    model = tf.keras.models.load_model('models/model_with_state_welltrained.keras')
    today = datetime.date.today().strftime('%Y-%m-%d')
    bill_pred = BillPrediction.objects.get_or_create(id = bill_id,creation_date = today)[0]
    query = Q(end_date = None)
    query.add(Q(end_date__gte = today), Q.OR)
    memberships = Membership.objects.filter(query)
    state_list = []
    party_list = []
    house_list = []
    for m in memberships:
        state_list.append(m.state)
        party_list.append(m.party)
        house_list.append(m.house)
    mem_df = pd.DataFrame({'state' : state_list, 'party': party_list, 'house' : house_list})
    mem_df = mem_df.groupby(by=['state','party','house'],as_index=False).size()
    feat_df = pd.DataFrame(0, index=np.arange(mem_df.shape[0]), columns=column_list, dtype='int8')
    d = asyncio.run(gatherFeatures(bill_id))
    if d == None : return -1
    for key in list(d.keys()):
        feat_df[key] = d[key]
    feat_df['question_On Passage'] = 1
    for index, row in mem_df.iterrows():
        feat_df.at[index, 'house'] = 0 if row['house'] else 1
        feat_df.at[index, 'party_' + row['party']] = 1
        feat_df.at[index, 'state_' + row['state']] = 1
    fit = model.predict(feat_df)
    fit = np.round(fit,5)
    objs = [None] * mem_df.shape[0]
    for index, row in mem_df.iterrows():
        objs[index] = BinaryProbability(
            bill_pred = bill_pred,
            state= row['state'],
            in_house = row['house'],
            party = row['party'],
            counts = row['size'],
            p = fit[index][0].item()
            )
    BinaryProbability.objects.bulk_create(objs)

def getPredictionBatch(bill_id, in_house, sample_size, run_sample = True):
    bill = Bill.objects.get(id = bill_id)
    _set = BillPrediction.objects.filter(id= bill_id)
    if not _set.exists() and createPredictions(bill_id) == -1: return None
    bill_pred = BillPrediction.objects.get(id=bill_id)
    if (bill.latest_action > bill_pred.creation_date):
        bill_pred.delete()
        createPredictions(bill_id)
        bill_pred = BillPrediction.objects.get(id=bill_id)
    if not run_sample: return
    p_funcs = BinaryProbability.objects.filter(bill_pred = bill_pred, in_house = in_house)
    if not p_funcs.exists():
        return -1
    batch = np.zeros(sample_size, dtype=np.int64)
    for p_func in p_funcs:
        rvs = binom.rvs(p_func.counts, float(p_func.p), size = sample_size)
        batch += rvs
    return batch.tolist()