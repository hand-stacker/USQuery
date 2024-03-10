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
from SenateQuery.models import Member, Congress, Senatorship, Representativeship
from USQuery import settings
from django.http import JsonResponse

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
            "sen_form": forms.SenatorForm(request.GET),
            "rep_form" : forms.RepresentativeForm(request.GET),
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
def search(request, congress_num, member_id, isSenateSearch):
    assert isinstance(request, HttpRequest)
    if isSenateSearch:
        role = "senate"
    else:
        role = "house"
    utils.updateMembership(congress_num, role, member_id)
    votes_response = utils.connect(settings.PROPUBLICA_DIR + "members/"+ member_id + "/votes.json?offset=0", "ProPublica")
    votes = []
    if (votes_response):
        for vote in votes_response[0]["votes"]:
            bill = vote["bill"]
            if bill:
                votes.append(("("+bill["bill_id"]+") "+str(bill["title"]), vote["description"], vote["position"]))
    # find senator given member id and congress num
    congress = Congress.objects.get(congress_num = congress_num)
    if isSenateSearch:
        member = congress.senators.get(id = member_id)
        membership = Senatorship.objects.get(congress = congress, senator = member)
    else:
        member = congress.representatives.get(id = member_id)
        membership = Representativeship.objects.get(congress = congress, representative = member)
    return render(
        request,
        'SenateQuery/senator.html',
        {
            'title': member.full_name,
            'year':datetime.now().year,
            'senator_name'  : member.full_name,
            'senator_party' : membership.party,
            'senator_state' : membership.state,
            'senator_short' : membership.short_title,
            'senator_title' : membership.long_title,
            'senator_start' : membership.start_date,
            'senator_end'   : membership.end_date,
            'senator_url'   : member.url,
            'senator_img'   : member.image_link,
            'senator_twt'   : member.twitter,
            'senator_fac'   : member.facebook,
            'senator_ytb'   : member.youtube,
            'senator_votes' : votes,
            'senator_phone' : member.phone,
            'senator_office': member.office,
            'senator_totalvotes': membership.total_votes,
            'senator_partyvotes': membership.total_votes * membership.party_votes_pct,
            'senator_nonpartyvotes'   : membership.total_votes * membership.nonparty_votes_pct,
            'congress_num'  : congress_num,
            'blob' : votes_response,
            
        }
    )
def populate_senators(request):
    assert isinstance(request, HttpRequest)
    utils.addMemberByCongressLazy(116, "senate")
    return HttpResponseRedirect("/")

def populate_representatives(request):
    assert isinstance(request, HttpRequest)
    utils.addMemberByCongressLazy(117, "house")
    return HttpResponseRedirect("/")

def query(request):
    senate_form = forms.SenatorForm(request.GET)
    if senate_form.is_valid():
        return search(request, senate_form.cleaned_data["congress"].congress_num, senate_form.cleaned_data["senator"].id, True)
    context = {
        'senate_form': senate_form
    }
    return render(request, 'senator-search-form.html', context)
    

def update_senators(request, congress_id):
    senators = Congress.objects.get(congress_num__exact=int(congress_id)).senators.values('id', 'full_name')
    return JsonResponse({'senators': list(senators)})

def rep_query(request):
    form = forms.RepresentativeForm(request.GET)
    if form.is_valid():
        return search(request, form.cleaned_data["congress"].congress_num, form.cleaned_data["representative"].id, False)