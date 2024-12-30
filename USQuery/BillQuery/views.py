from django.shortcuts import render
from django.http import HttpRequest, HttpResponseRedirect
from datetime import datetime
from app import utils, forms
from BillQuery.models import Vote, Choice, ChoiceVote
from USQuery import settings
from django.http import JsonResponse
from json import dumps
# Create your views here.

def home(request):
    """Renders the home page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'BillQuery/index.html',
        {   
            'title':"Bill Query", 
            'content':"Make a bill Query",
            'year':datetime.now().year,
            "cong_form": forms.CongressForm,
            "date_form": forms.DateForm(request.GET),
        }
    )

def about(request):
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'BillQuery/about.html',
        {   
            'title':"About Bill Query",
            'content':"About Bill Query",
            'year':datetime.now().year,
        }
    )

def search(request):
    date_form = forms.DateForm(request.GET)
    blob = utils.getBillsInRange(
                date_form.data["start_date_day"],
                date_form.data["start_date_month"],
                date_form.data["start_date_year"],
                date_form.data["end_date_day"],
                date_form.data["end_date_month"],
                date_form.data["end_date_year"],
                )
    content = utils.convertBillData(blob['bills'])
    
    pagination = blob['bills']
    #content = dumps(content)
    return render(
        request,
        'BillQuery/bills.html',
        {   
            'title':"Results",
            'bill_data': content,
            'pagination' : pagination,
            'year':datetime.now().year,
        }
    )

def bill(request, congress_id, type, num):
    assert isinstance(request, HttpRequest)
    apiURL  ="https://api.congress.gov/v3/bill/" + str(congress_id) + "/" + type + "/" + str(num)
    API_response = utils.getBill(apiURL)
    return render(
        request,
        'BillQuery/bill.html',
        {   
            'title':"CONGRESS:" + str(congress_id) + "-" + type + ":" + str(num),
            'content' : API_response,
            'year':datetime.now().year,
        }
    )
    