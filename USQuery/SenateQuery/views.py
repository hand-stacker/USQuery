import http
from django.shortcuts import render
from django.http import HttpRequest
from datetime import datetime
from SenateQuery import congconnect as conn

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
def query(request):
    assert isinstance(request, HttpRequest)
    req = requst[0]
    s_pack = conn.connect(req)
    return render(
        request,
        'SenateQuery/senator.html',
        {'title':"About Senate Query",
            'content':"About Senate Query",
            'year':datetime.now().year,
            'senator-name' : 'a',
        }
    )
