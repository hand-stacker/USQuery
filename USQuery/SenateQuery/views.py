from abc import ABCMeta
from asyncio.windows_events import NULL
import http
from pydoc import resolve
from re import A
from unittest import result
from urllib import request
from django.http.response import HttpResponseBase
from django.shortcuts import render
from django.http import HttpRequest, HttpResponseRedirect
from datetime import datetime
from app import utils, forms
from SenateQuery.models import Member, Congress, Membership
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
    API_response = utils.updateMember(congress_num, member_id)

    
    ## votes_response = utils.connect(settings.PROPUBLICA_DIR + "members/"+ member_id + "/votes.json?offset=0", "ProPublica")
    votes = []
    '''
    if (votes_response):
        for vote in votes_response[0]["votes"]:
            bill = vote["bill"]
            if bill:
                votes.append(("("+bill["bill_id"]+") "+str(bill["title"]), vote["description"], vote["position"]))
                '''
    # find senator given member id and congress num
    congress = Congress.objects.get(congress_num = congress_num)
    member = congress.members.get(id = member_id)
    membership = Membership.objects.get(congress = congress, member = member)
    return render(
        request,
        'SenateQuery/representative.html',
        {
            'title': member.full_name,
            'year':datetime.now().year,
            'rep_name'  : member.full_name,
            'rep_title' : 'Senator' if isSenateSearch else "Representative",
            'rep_party' : membership.party,
            'rep_district' : membership.district_num,
            'rep_state' : membership.state,
            'rep_start' : membership.start_date,
            'rep_end'   : membership.end_date,
            'rep_img'   : member.image_link,
            'rep_twt'   : member.twitter,
            'rep_fac'   : member.facebook,
            'rep_ytb'   : member.youtube,
            'rep_votes' : votes,
            'rep_phone' : member.phone,
            'rep_office': member.office,
            'congress_num'  : congress_num,
            'rep_url' : member.official_link,
        }
    )
    
    
def populate_congress(request, congress_id = 116):
    assert isinstance(request, HttpRequest) 
    utils.addMembersCongressAPILazy(congress_id)
    return HttpResponseRedirect("/")

def query(request):
    senate_form = forms.SenatorForm(request.GET)
    if senate_form.is_valid():
        return search(request, senate_form.cleaned_data["congress_sen"].congress_num, senate_form.cleaned_data["senator"].id, True)
    # have to not make response\
    return HttpResponseRedirect('/member-query/')

def rep_query(request):
    form = forms.RepresentativeForm(request.GET)
    if form.is_valid():
        return search(request, form.cleaned_data["congress_rep"].congress_num, form.cleaned_data["representative"].id, False)
    return HttpResponseRedirect('/member-query/')

def update_senators(request, congress_id):
    senators = Congress.objects.get(congress_num__exact=int(congress_id)).members.filter(membership__chamber = 'Senate').values('id', 'full_name')
    return JsonResponse({'senators': list(senators)})

def update_reps(request, congress_id):
    reps = Congress.objects.get(congress_num__exact=int(congress_id)).members.filter(membership__chamber = 'House of Representatives').values('id', 'full_name')
    return JsonResponse({'representatives': list(reps)})