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
column_list = ['house',
 'party_Democratic',
 'party_Independent',
 'party_Libertarian',
 'party_Republican',
 'state_AK',
 'state_AL',
 'state_AR',
 'state_AS',
 'state_AZ',
 'state_CA',
 'state_CO',
 'state_CT',
 'state_DC',
 'state_DE',
 'state_FL',
 'state_GA',
 'state_GU',
 'state_HI',
 'state_IA',
 'state_ID',
 'state_IL',
 'state_IN',
 'state_KS',
 'state_KY',
 'state_LA',
 'state_MA',
 'state_MD',
 'state_ME',
 'state_MI',
 'state_MN',
 'state_MO',
 'state_MP',
 'state_MS',
 'state_MT',
 'state_NC',
 'state_ND',
 'state_NE',
 'state_NH',
 'state_NJ',
 'state_NM',
 'state_NV',
 'state_NY',
 'state_OH',
 'state_OK',
 'state_OR',
 'state_PA',
 'state_PR',
 'state_RI',
 'state_SC',
 'state_SD',
 'state_TN',
 'state_TX',
 'state_UT',
 'state_VA',
 'state_VI',
 'state_VT',
 'state_WA',
 'state_WI',
 'state_WV',
 'state_WY',
 'Abortion',
 'Academic performance and assessments',
 'Accidents',
 'Accounting and auditing',
 'Administrative law and regulatory procedures',
 'Administrative remedies',
 'Adoption and foster care',
 'Adult day care',
 'Adult education and literacy',
 'Advanced technology and technological innovations',
 'Advisory bodies',
 'Age discrimination',
 'Aging',
 'Agricultural conservation and pollution',
 'Agricultural education',
 'Agricultural equipment and machinery',
 'Agricultural insurance',
 'Agricultural marketing and promotion',
 'Agricultural practices and innovations',
 'Agricultural prices, subsidies, credit',
 'Agricultural research',
 'Agricultural trade',
 'Air quality',
 'Alaska Natives and Hawaiians',
 'Alcoholic beverages',
 'Allergies',
 'Alliances',
 'Allied health services',
 'Alternative and renewable resources',
 'Alternative dispute resolution, mediation, arbitration',
 'Alternative treatments',
 'Animal and plant health',
 'Animal protection and human-animal relationships',
 'Appropriations',
 'Aquaculture',
 'Aquatic ecology',
 'Arab-Israeli relations',
 'Archaeology and anthropology',
 'Architecture',
 'Arctic and polar regions',
 'Area studies and international education',
 'Arms control and nonproliferation',
 'Art, artists, authorship',
 'Assault and harassment offenses',
 'Astronomy',
 'Athletes',
 'Atmospheric science and weather',
 'Aviation and airports',
 'Bank accounts, deposits, capital',
 'Banking and financial institutions regulation',
 'Bankruptcy',
 'Behavioral sciences',
 'Biological and life sciences',
 'Birds',
 'Birth defects',
 'Blood and blood diseases',
 'Books and print media',
 'Border security and unlawful immigration',
 'Broadcasting, cable, digital technologies',
 'Budget deficits and national debt',
 'Budget process',
 'Building construction',
 'Business education',
 'Business ethics',
 'Business expenses',
 'Business investment and capital',
 'Business records',
 'Buy American requirements',
 'Cancer',
 'Capital gains tax',
 'Cardiovascular and respiratory health',
 'Cell biology and embryology',
 'Cemeteries and funerals',
 'Census and government statistics',
 'Charitable contributions',
 'Chemical and biological weapons',
 'Chemistry',
 'Child care and development',
 'Child health',
 'Child safety and welfare',
 'Citizenship and naturalization',
 'Civics education',
 'Civil actions and liability',
 'Civil disturbances',
 'Climate change and greenhouse gases',
 'Coal',
 'Coast guard',
 'Collective security',
 'Commemorative events and holidays',
 'Commodities markets',
 'Community life and organization',
 'Commuting',
 'Competition and antitrust',
 'Competitiveness, trade promotion, trade deficits',
 'Comprehensive health care',
 'Computer security and identity theft',
 'Computers and information technology',
 'Conflicts and wars',
 'Congressional agencies',
 'Congressional committees',
 'Congressional districts and representation',
 'Congressional elections',
 'Congressional leadership',
 'Congressional officers and employees',
 'Congressional operations and organization',
 'Congressional oversight',
 'Congressional tributes',
 'Congressional-executive branch relations',
 'Constitution and constitutional amendments',
 'Consumer affairs',
 'Consumer credit',
 'Contracts and agency',
 'Cooperative and condominium housing',
 'Corporate finance and management',
 'Correctional facilities and imprisonment',
 'Cosmetics and personal care',
 'Credit and credit markets',
 'Crime prevention',
 'Crime victims',
 'Crimes against animals and natural resources',
 'Crimes against children',
 'Crimes against property',
 'Crimes against women',
 'Criminal investigation, prosecution, interrogation',
 'Criminal justice information and records',
 'Criminal procedure and sentencing',
 'Cultural exchanges and relations',
 'Currency',
 'Customs enforcement',
 'Dams and canals',
 'Debt collection',
 'Defense spending',
 'Dental care',
 'Detention of persons',
 'Digestive and metabolic diseases',
 'Digital media',
 'Diplomacy, foreign officials, Americans abroad',
 'Disability and health-based discrimination',
 'Disability and paralysis',
 'Disability assistance',
 'Disaster relief and insurance',
 'Domestic violence and child abuse',
 'Drug safety, medical device, and laboratory regulation',
 'Drug therapy',
 'Drug trafficking and controlled substances',
 'Drug, alcohol, tobacco use',
 'Due process and equal protection',
 'Earth sciences',
 'Ecology',
 'Economic development',
 'Economic performance and conditions',
 'Economic theory',
 'Education of the disadvantaged',
 'Education programs funding',
 'Educational facilities and institutions',
 'Educational guidance',
 'Educational technology and distance education',
 'Elections, voting, political campaign regulation',
 'Electric power generation and transmission',
 'Elementary and secondary education',
 'Emergency communications systems',
 'Emergency medical services and trauma care',
 'Emergency planning and evacuation',
 'Employee benefits and pensions',
 'Employee hiring',
 'Employee leave',
 'Employee performance',
 'Employment and training programs',
 'Employment discrimination and employee rights',
 'Employment taxes',
 'Endangered and threatened species',
 'Energy assistance for the poor and aged',
 'Energy efficiency and conservation',
 'Energy prices',
 'Energy research',
 'Energy revenues and royalties',
 'Energy storage, supplies, demand',
 'Environmental assessment, monitoring, research',
 'Environmental education',
 'Environmental health',
 'Environmental regulatory procedures',
 'Environmental technology',
 'Espionage and treason',
 'Ethnic studies',
 'Evidence and witnesses',
 'Executive agency funding and structure',
 'Family planning and birth control',
 'Family relationships',
 'Family services',
 'Farmland',
 'Federal appellate courts',
 'Federal district courts',
 'Federal officials',
 'Federal preemption',
 'Federal-Indian relations',
 'Federally chartered organizations',
 'Financial crises and stabilization',
 'Financial literacy',
 'Financial services and investments',
 'Firearms and explosives',
 'Fires',
 'First Amendment rights',
 'First responders and emergency personnel',
 'Fishes',
 'Floods and storm protection',
 'Food assistance and relief',
 'Food industry and services',
 'Food supply, safety, and labeling',
 'Foreign aid and international relief',
 'Foreign and international banking',
 'Foreign and international corporations',
 'Foreign labor',
 'Foreign language and bilingual programs',
 'Foreign loans and debt',
 'Foreign property',
 'Forests, forestry, trees',
 'Fraud offenses and financial crimes',
 'Free trade and trade barriers',
 'Freedom of information',
 'Fruit and vegetables',
 'Gambling',
 'Games and hobbies',
 'General Native American affairs matters',
 'General agriculture matters',
 'General business and commerce matters',
 'General education matters',
 'General energy matters',
 'General foreign operations matters',
 'General health and health care finance matters',
 'General public lands matters',
 'General science and technology matters',
 'General taxation matters',
 'Genetics',
 'Geography and mapping',
 'Government buildings, facilities, and property',
 'Government corporations and government-sponsored enterprises',
 'Government employee pay, benefits, personnel management',
 'Government ethics and transparency, public corruption',
 'Government information and archives',
 'Government lending and loan guarantees',
 'Government liability',
 'Government studies and investigations',
 'Government trust funds',
 'Grain',
 'HIV/AIDS',
 'Hate crimes',
 'Hazardous wastes and toxic substances',
 'Health care costs and insurance',
 'Health care coverage and access',
 'Health care quality',
 'Health facilities and institutions',
 'Health information and medical records',
 'Health personnel',
 'Health programs administration and funding',
 'Health promotion and preventive care',
 'Health technology, devices, supplies',
 'Hearing, speech, and vision care',
 'Hereditary and development disorders',
 'Higher education',
 'Historic sites and heritage areas',
 'Historical and cultural resources',
 'Home and outpatient care',
 'Homeland security',
 'Homelessness and emergency shelter',
 'Horticulture and plants',
 'Hospital care',
 'House of Representatives',
 'Housing and community development funding',
 'Housing discrimination',
 'Housing finance and home ownership',
 'Housing for the elderly and disabled',
 'Housing industry and standards',
 'Housing supply and affordability',
 'Human rights',
 'Human trafficking',
 'Humanities programs funding',
 'Hunting and fishing',
 'Hybrid, electric, and advanced technology vehicles',
 'Hydrology and hydrography',
 'Immigrant health and welfare',
 'Immigration status and procedures',
 'Immunology and vaccination',
 'Income tax credits',
 'Income tax deductions',
 'Income tax deferral',
 'Income tax exclusion',
 'Income tax rates',
 'Indian claims',
 'Indian lands and resources rights',
 'Indian social and development programs',
 'Industrial facilities',
 'Industrial policy and productivity',
 'Infectious and parasitic diseases',
 'Inflation and prices',
 'Infrastructure development',
 'Insects',
 'Insurance industry and regulation',
 'Intellectual property',
 'Intelligence activities, surveillance, classified information',
 'Interest, dividends, interest rates',
 'Intergovernmental relations',
 'International exchange and broadcasting',
 'International law and treaties',
 'International monetary system and foreign exchange',
 'International organizations and cooperation',
 'International scientific cooperation',
 'Internet, web applications, social media',
 'Judges',
 'Judicial procedure and administration',
 'Judicial review and appeals',
 'Jurisdiction and venue',
 'Juvenile crime and gang violence',
 'Labor market',
 'Labor standards',
 'Labor-management relations',
 'Lakes and rivers',
 'Land transfers',
 'Land use and conservation',
 'Landlord and tenant',
 'Language arts',
 'Law enforcement administration and funding',
 'Law enforcement officers',
 'Lawyers and legal services',
 'Lease and rental services',
 'Legal fees and court costs',
 'Legislative rules and procedure',
 'Libraries and archives',
 'Licensing and registrations',
 'Life, casualty, property insurance',
 'Lighting, heating, cooling',
 'Literature',
 'Livestock',
 'Long-term, rehabilitative, and terminal care',
 'Low- and moderate-income housing',
 'Mammals',
 'Manufacturing',
 'Marine and coastal resources, fisheries',
 'Marine and inland water transportation',
 'Marine pollution',
 'Marketing and advertising',
 'Marriage and family status',
 'Materials',
 'Meat',
 'Medicaid',
 'Medical education',
 'Medical ethics',
 'Medical research',
 'Medical tests and diagnostic methods',
 'Medicare',
 'Members of Congress',
 'Mental health',
 'Metals',
 'Migrant, seasonal, agricultural labor',
 'Military assistance, sales, and agreements',
 'Military civil functions',
 'Military command and structure',
 'Military education and training',
 'Military facilities and property',
 'Military history',
 'Military law',
 'Military medicine',
 'Military operations and strategy',
 'Military personnel and dependents',
 'Military procurement, research, weapons development',
 'Military readiness',
 'Militias and paramilitary groups',
 'Mining',
 'Minority and disadvantaged businesses',
 'Minority education',
 'Minority employment',
 'Minority health',
 'Missing persons',
 'Monetary policy',
 'Monuments and memorials',
 'Motor carriers',
 'Motor fuels',
 'Motor vehicles',
 'Multilateral development programs',
 'Musculoskeletal and skin diseases',
 'Museums, exhibitions, cultural centers',
 'Music',
 'National Guard and reserves',
 'National and community service',
 'National symbols',
 'Natural disasters',
 'Navigation, waterways, harbors',
 'Neurological disorders',
 'News media and reporting',
 'Noise pollution',
 'Normal trade relations, most-favored-nation treatment',
 'Nuclear power',
 'Nuclear weapons',
 'Nursing',
 'Nutrition and diet',
 'Oil and gas',
 'Olympic games',
 'Organ and tissue donation and transplantation',
 'Organized crime',
 'Outdoor recreation',
 'Palestinians',
 'Parks, recreation areas, trails',
 'Pedestrians and bicycling',
 'Performance measurement',
 'Performing arts',
 'Personnel records',
 'Pest management',
 'Photography and imaging',
 'Physical fitness and lifestyle',
 'Pipelines',
 'Policy sciences',
 'Political advertising',
 'Political movements and philosophies',
 'Political parties and affiliation',
 'Political representation',
 'Pollution liability',
 'Pornography',
 'Postal service',
 'Poverty and welfare assistance',
 'Preschool education',
 'Prescription drugs',
 'Presidential administrations',
 'Presidents and presidential powers, Vice Presidents',
 'Private Legislation',
 'Product development and innovation',
 'Product safety and quality',
 'Professional sports',
 'Property rights',
 'Property tax',
 'Protection of officials',
 'Protest and dissent',
 'Public contracts and procurement',
 'Public housing',
 'Public participation and lobbying',
 'Public transit',
 'Public utilities and utility rates',
 'Public-private cooperation',
 'Racial and ethnic relations',
 'Radiation',
 'Radio spectrum allocation',
 'Radioactive wastes and releases',
 'Railroads',
 'Real estate business',
 'Reconstruction and stabilization',
 'Refugees, asylum, displaced persons',
 'Regional and metropolitan planning',
 'Religion',
 'Reptiles',
 'Research administration and funding',
 'Research and development',
 'Research ethics',
 'Residential rehabilitation and home repair',
 'Retail and wholesale trades',
 'Right of privacy',
 'Roads and highways',
 'Rule of law and government transparency',
 'Rural conditions and development',
 'Sales and excise taxes',
 'Sanctions',
 'School administration',
 'School athletics',
 'Science and engineering education',
 'Scientific communication',
 'Seafood',
 'Seashores and lakeshores',
 'Securities',
 'Self-employed',
 'Senate',
 'Separation, divorce, custody, support',
 'Service animals',
 'Service industries',
 'Sex and reproductive health',
 'Sex offenses',
 'Sex, gender, sexual orientation discrimination',
 'Sexually transmitted diseases',
 'Small business',
 'Small towns',
 'Smuggling and trafficking',
 'Social security and elderly assistance',
 'Social work, volunteer service, charitable organizations',
 'Soil pollution',
 'Solid waste and recycling',
 'Sound recording',
 'Sovereignty, recognition, national governance and status',
 'Space flight and exploration',
 'Spacecraft and satellites',
 'Special education',
 'Specialized courts',
 'Sports and recreation facilities',
 'State and local courts',
 'State and local finance',
 'State and local government operations',
 'State and local taxation',
 'Strategic materials and reserves',
 'Student aid and college costs',
 'Student records',
 'Subversive activities',
 'Supreme Court',
 'Surgery and anesthesia',
 'Tariffs',
 'Tax administration and collection, taxpayers',
 'Tax reform and tax simplification',
 'Tax treatment of families',
 'Tax-exempt organizations',
 'Taxation of foreign income',
 'Teaching, teachers, curricula',
 'Technology assessment',
 'Technology transfer and commercialization',
 'Teenage pregnancy',
 'Telecommunication rates and fees',
 'Telephone and wireless communication',
 'Television and film',
 'Temporary and part-time employment',
 'Terrorism',
 'Time and calendar',
 'Trade adjustment assistance',
 'Trade agreements and negotiations',
 'Trade restrictions',
 'Trade secrets and economic espionage',
 'Transfer and inheritance taxes',
 'Transportation costs',
 'Transportation employees',
 'Transportation programs funding',
 'Transportation safety and security',
 'Travel and tourism',
 'U.S. Capitol',
 'U.S. and foreign investments',
 'U.S. history',
 'U.S. territories and protectorates',
 'Unemployment',
 'Urban and suburban affairs and development',
 'User charges and fees',
 "Veterans' education, employment, rehabilitation",
 "Veterans' loans, housing, homeless programs",
 "Veterans' medical care",
 "Veterans' organizations and recognition",
 "Veterans' pensions and compensation",
 'Veterinary medicine and animal diseases',
 'Violent crime',
 'Visas and passports',
 'Vocational and technical education',
 'Voting rights',
 'Wages and earnings',
 'War and emergency powers',
 'War crimes, genocide, crimes against humanity',
 'Water quality',
 'Water resources funding',
 'Water storage',
 'Water use and supply',
 'Watersheds',
 'Wetlands',
 'White-collar crime',
 'Wilderness and natural areas, wildlife refuges, wild rivers, habitats',
 'Wildlife conservation and habitat protection',
 'Women in business',
 "Women's education",
 "Women's employment",
 "Women's health",
 "Women's rights",
 'Worker safety and health',
 'World health',
 'World history',
 'Youth employment and child labor',
 'question_On Agreeing to the Conference Report',
 'question_On Agreeing to the Resolution',
 'question_On Agreeing to the Resolution, as Amended',
 'question_On Cloture on the Motion to Proceed',
 'question_On Motion to Concur in the Senate Amendment',
 'question_On Motion to Recommit',
 'question_On Motion to Recommit with Instructions',
 'question_On Motion to Refer',
 'question_On Motion to Suspend the Rules and Agree',
 'question_On Motion to Suspend the Rules and Agree, as Amended',
 'question_On Motion to Suspend the Rules and Concur in the Senate Amendment',
 'question_On Motion to Suspend the Rules and Pass',
 'question_On Motion to Suspend the Rules and Pass, as Amended',
 'question_On Motion to Table',
 'question_On Ordering the Previous Question',
 'question_On Overriding the Veto',
 'question_On Passage',
 'question_On Passage of the Bill',
 'question_On the Cloture Motion',
 'question_On the Joint Resolution',
 'question_On the Motion',
 'question_On the Motion to Discharge',
 'question_On the Motion to Proceed',
 'question_On the Resolution',
 'question_Passage, Objections of the President To The Contrary Notwithstanding',
 'question_Table Motion to Reconsider']

prompt = secretss.prompt
column_dict = {col: index for index, col in enumerate(column_list)}
model = 'gemini-2.5-flash'

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
    client = genai.Client(api_key=settings.GEMINI_KEY)
    generate_content_config = types.GenerateContentConfig(response_mime_type='text/plain')
    mult = 1 if bill_id < 99_999_999 else 10
    congress_num = bill_id // (100000 * mult)
    type_enum = (bill_id // (10000 * mult)) % 10
    bill_type = types_list[type_enum]
    bill_num = bill_id % (10000 * mult)
    fullpath = settings.CONGRESS_DIR + 'bill/' + str(congress_num) + '/' + bill_type + '/' + str(bill_num)
    try:
        blob = await utils.run_concurrent_connect(session, [fullpath + '/text?', fullpath + '/subjects?'], header_str)
        subjects = blob[1]
        texts = blob[0]

        if len(texts['textVersions']) == 0 or len(subjects['subjects']['legislativeSubjects']) == 0:
            return None

        subj_litr = '['
        for subject in subjects['subjects']['legislativeSubjects']:
            subj_litr += '"' + subject['name'] + '",'
        subj_litr += ']'

        indx = -1
        date_max = datetime.datetime(1, 1, 1, 1, 1, 1)
        for j in range(len(texts['textVersions'])):
            date_str = texts['textVersions'][j]['date']
            if date_str is None:
                continue
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
        if txt_html is None:
            return None

        soup = BeautifulSoup(txt_html)
        version_text = soup.get_text()
        version_text = version_text.replace('\n', '').replace('_', '')
        version_text = re.sub(pattern, ' ', version_text)
        ctns = [version_text, subj_litr, prompt]

        # Use synchronous genai calls inside a thread so we don't depend on an async client API.
        try:
            token_count = await asyncio.to_thread(client.models.count_tokens, model=model, contents=ctns)
        except Exception:
            return None

        if getattr(token_count, 'total_tokens', None) is not None and token_count.total_tokens > 250_000:
            return None

        try:
            response = await asyncio.to_thread(lambda: client.models.generate_content(model=model, contents=ctns, config=generate_content_config))
        except Exception:
            return None

        response = response.text
        response = response.removeprefix('```python')
        response = response.removesuffix('```')
        response = response.removesuffix('```\n')

        try:
            d = ast.literal_eval(response)
        except Exception:
            return None

        for key in list(d.keys()):
            if key not in column_dict:
                d.pop(key)

        return d
    finally:
        await session.close()

tf_model = tf.keras.models.load_model('models/model_with_state_welltrained.keras')
# returns -1 if any errors occured, 1 if creation was successfull
def createPredictions(bill_id):
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
    fit = tf_model.predict(feat_df)
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

# gets sample_size batch of vote simulations. 
# assumes bill exists
# when bill has passes deletes any BillPrediction objects an returns None
# when Errors occur returns None
def getPredictionBatch(bill_id, in_house, sample_size, run_sample = True):
    bill = Bill.objects.get(id = bill_id)
    _set = BillPrediction.objects.filter(id= bill_id)
    if bill.status : 
        if _set.exists():
            deletePred(bill_id)
        return None

    if not _set.exists() and createPredictions(bill_id) == -1: return None
    bill_pred = BillPrediction.objects.get(id=bill_id)
    # if new actions maybe new text file, thus BillPrediction is recreated
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

# Deletes BillPrediction (assumes this prediction exists)
def deletePred(bill_id):
    bill_pred = BillPrediction.objects.get(id=bill_id)
    bill_pred.delete()