from datetime import datetime
from urllib import request
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import HttpRequest, HttpResponseRedirect
from SenateQuery.models import Congress
from BillQuery.models import Vote
from app import siteutils, utils

def home(request):
    """Renders the home page."""
    assert isinstance(request, HttpRequest)
    try:
        congress = Congress.objects.get(congress_num = 119)
    except:
        return HttpResponseRedirect('/member-query')
    vote_list = Vote.objects.filter(congress = congress)[0:16].all()
    vote_table = utils.voteTablePage(vote_list)
    return render(
        request,
        'app/index.html',
        {
            'title':'Home Page',
            'vote_table' : vote_table,
        }
    )

def contact(request):
    """Renders the contact page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/contact.html',
        {
            'title':'Contact',
        }
    )

def about(request):
    """Renders the about page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/about.html',
        {
            'title':'About',
        }
    )

@staff_member_required
def updateJSON(request, congress_id) : 
    assert isinstance(request, HttpRequest)
    siteutils.modifyCountyGeoJSON(congress_id)
    return HttpResponseRedirect("/")

@staff_member_required
def updateSTATES(request) : 
    assert isinstance(request, HttpRequest)
    siteutils.modifyStateGeoJSON()
    return HttpResponseRedirect("/")
