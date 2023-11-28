import requests, json
from USQuery import settings
from requests.exceptions import HTTPError
def connect(path):
    url = settings.CONGRESS_DIR + path
    
    try:
        response = requests.get(url, headers={'X-API-Key': settings.CONGRESS_KEY}, timeout=20)
        response.raise_for_status()
    except HTTPError as http_err:
        print(f'HTTP ERROR : {http_err}')
    except Exception as err:
        print(f'MISC ERROR : {err}')
    except TimeoutError:
        print("TIMEOUT ERROR")
    else:
        return response.json()['results']


