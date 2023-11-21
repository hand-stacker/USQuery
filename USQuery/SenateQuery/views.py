import http
from urllib import request
from django.shortcuts import render
from django.http import HttpRequest
from datetime import datetime
from SenateQuery import addsenators
from SenateQuery.models import Senator

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
def search(request):
    assert isinstance(request, HttpRequest)
    congress_num = "117"
    member_id = "S000033"
    senator = Senator.objects.get(id=member_id)
    return render(
        request,
        'SenateQuery/senator.html',
        {
            'title': senator.full_name,
            'year':datetime.now().year,
            'senator_name' : senator.full_name,
            'senator_party' : senator.party,
            'senator_state' : senator.state,
            'senator_terms' : '1000 BC - 2023',
            'blob' : senator.birth_date,
            
        }
    )
def populate(request):
    assert isinstance(request, HttpRequest)
    addsenators
    return home(request)
