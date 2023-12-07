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
from SenateQuery.models import Senator, Congress, Senatorship
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
    votes_response = utils.connect(settings.PROPUBLICA_DIR + "members/"+ member_id + "/votes.json", "ProPublica")
    votes = []
    for vote in votes_response[0]["votes"]:
        votes.append(("("+vote["bill"]["bill_id"]+") "+str(vote["bill"]["title"]), vote["description"], vote["position"]))
    # find senator given member id and congress num
    congress = Congress.objects.get(congress_num = congress_num)
    senator = congress.senators.get(id = member_id)
    senatorship = Senatorship.objects.get(congress = congress, senator = senator)
    return render(
        request,
        'SenateQuery/senator.html',
        {
            'title': senator.name,
            'year':datetime.now().year,
            'senator_name'  : senator.name,
            'senator_party' : senatorship.party,
            'senator_state' : senatorship.state,
            'senator_short' : senatorship.short_title,
            'senator_title' : senatorship.long_title,
            'senator_start' : senatorship.start_date,
            'senator_end'   : senatorship.end_date,
            'senator_url'   : senator.url,
            'senator_img'   : senator.image_link,
            'senator_twt'   : senator.twitter,
            'senator_fac'   : senator.facebook,
            'senator_ytb'   : senator.youtube,
            'senator_votes' : votes,
            'senator_phone' : senator.phone,
            'senator_office': senator.office,
            'senator_totalvotes': senatorship.total_votes,
            'senator_partyvotes': senatorship.total_votes * senatorship.party_votes_pct,
            'senator_nonpartyvotes'   : senatorship.total_votes * senatorship.nonparty_votes_pct,
            'blob' : votes_response,
            
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