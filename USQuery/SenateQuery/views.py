from asyncio.windows_events import NULL
import http
from pydoc import resolve
from urllib import request
from django.http.response import HttpResponseBase
from django.shortcuts import render
from django.http import HttpRequest, HttpResponseRedirect
from datetime import datetime
from app import utils, forms
from SenateQuery import addsenators, congconnect
from SenateQuery.models import Senator, Congress

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
    congress_chamber = "Senate"
    index = -1
    response = congconnect.connect("members/" + member_id + ".json")
    response = response[0]
    for i in range(len(response['roles'])):
        if (response['roles'][i]['congress'] == congress_num) & (response['roles'][i]['chamber'] == congress_chamber): 
            index = i
            break
    if index == -1:
        print("FATAL DATABASE ERROR")
    senator_name = utils.makeFullName(
                                      response['first_name'],
                                      response['last_name'],
                                      response['middle_name'],
                                      response['suffix'],
                                      response['roles'][index]['short_title'])
    return render(
        request,
        'SenateQuery/senator.html',
        {
            'title': senator_name,
            'year':datetime.now().year,
            'senator_name' : senator_name,
            'senator_party' : response['roles'][index]['party'],
            'senator_state' : response['roles'][index]['state'],
            'senator_terms' : '1000 BC - 2023',
            'blob' : response,
            
        }
    )
def populate(request):
    assert isinstance(request, HttpRequest)
    addsenators.add(117)
    return HttpResponseRedirect("/")

def query(request):
    form = forms.SenatorForm(request.GET)
    if form.is_valid():
        return search(request, form.cleaned_data["congress"].congress_num, form.cleaned_data["senator"].id)