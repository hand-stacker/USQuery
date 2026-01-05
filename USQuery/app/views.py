from datetime import datetime
from urllib import request
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import HttpRequest, HttpResponseRedirect, HttpResponse
from django.views.decorators.http import require_GET
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

@require_GET
def robots_txt(request):
    content = """ 
User-agent: *
Disallow: /admin
Disallow: /admin/
Disallow: /admin*
Disallow: /admin/*
Disallow: /login
Disallow: /login/
Disallow: /login*
Disallow: /login/*
Disallow: /logout
Disallow: /logout*
Disallow: /logout/
Disallow: /logout/*
Disallow: /member-query/update-mems
Disallow: /member-query/update-mems/
Disallow: /member-query/update-mems*
Disallow: /member-query/update-mems/*
Disallow: /bill-query/prediction-request
Disallow: /bill-query/prediction-request/
Disallow: /bill-query/prediction-request*
Disallow: /bill-query/prediction-request/*
Disallow: /bill-query/bill
Disallow: /bill-query/bill/
Disallow: /bill-query/bill*
Disallow: /bill-query/bill/*
Disallow: /bill-query/vote
Disallow: /bill-query/vote/
Disallow: /bill-query/vote*
Disallow: /bill-query/vote/*
Allow: /bill-query/bill/119
Allow: /bill-query/bill/119/
Allow: /bill-query/bill/119*
Allow: /bill-query/bill/119/*
Allow: /bill-query/vote/119*

Crawl-delay: 10
    """
    return HttpResponse(content, content_type="text/plain")
