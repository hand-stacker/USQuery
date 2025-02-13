from datetime import datetime
from urllib import request
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import HttpRequest, HttpResponseRedirect
from app import siteutils

def home(request):
    """Renders the home page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/index.html',
        {
            'title':'Home Page',
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
