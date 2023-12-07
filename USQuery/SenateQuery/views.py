from asyncio.windows_events import NULL
import http
from pydoc import resolve
from unittest import result
from urllib import request
from django.http.response import HttpResponseBase
from django.shortcuts import render
from django.http import HttpRequest, HttpResponseRedirect
from datetime import datetime
from app import utils, forms
from SenateQuery.models import Senator, Congress
from USQuery import settings

# Create your views here.
def home(request):
    """Renders the home page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'SenateQuery/index.html',
        {   
            'title':"Senate Query", 
            'content':"Make a senate Query",
            'year':datetime.now().year,
            "form": forms.SenatorForm(request.GET)
        }
    )

def about(request):
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'SenateQuery/about.html',
        {   
            'title':"About Senate Query",
            'content':"About Senate Query",
            'year':datetime.now().year,
        }
    )
def search(request, congress_num, member_id):
    assert isinstance(request, HttpRequest)
    response = utils.connect(settings.PROPUBLICA_DIR + "members/" + member_id + ".json", "ProPublica")[0]
    votes_response = utils.connect(settings.PROPUBLICA_DIR + "members/"+ member_id + "/votes.json", "ProPublica")
    votes_response = votes_response[0]["votes"]
    votes = []
    for vote in votes_response:
        votes.append(("("+vote["bill"]["bill_id"]+") "+str(vote["bill"]["title"]), vote["description"], vote["position"]))
    index = utils.findIndexOfRoleByChamberAndCongress(response['roles'], congress_num, 'Senate')
    if index == -1:
        print("FATAL DATABASE ERROR")
    senator_name = utils.makeFullName(
                                      response['first_name'],
                                      response['last_name'],
                                      response['middle_name'],
                                      response['suffix'],
                                      )
    return render(
        request,
        'SenateQuery/senator.html',
        {
            'title': senator_name,
            'year':datetime.now().year,
            'senator_name'  : senator_name,
            'senator_party' : response['roles'][index]['party'],
            'senator_state' : response['roles'][index]['state'],
            'senator_short' : response['roles'][index]['short_title'],
            'senator_title' : response['roles'][index]['title'],
            'senator_start' : response['roles'][index]['start_date'],
            'senator_end'   : response['roles'][index]['end_date'],
            'senator_url'   : response['url'],
            'senator_twt'   : response['twitter_account'],
            'senator_fac'   : response['facebook_account'],
            'senator_ytb'   : response['youtube_account'],
            'senator_votes' : votes,
            'senator_phone' : response['roles'][0]['phone'],
            'senator_office': response['roles'][0]['office'],
            'senator_totalvotes': response['roles'][index]['total_votes'],
            'senator_partyvotes': response['roles'][index]['votes_with_party_pct'],
            'senator_nonpartyvotes'   : response['roles'][index]['votes_against_party_pct'],
            'blob' : response,
            
        }
    )
def populate(request):
    assert isinstance(request, HttpRequest)
    utils.addSenatorsByCongress(117)
    return HttpResponseRedirect("/")

def query(request):
    form = forms.SenatorForm(request.GET)
    if form.is_valid():
        return search(request, form.cleaned_data["congress"].congress_num, form.cleaned_data["senator"].id)