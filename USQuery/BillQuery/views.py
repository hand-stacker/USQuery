from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponseRedirect
from datetime import datetime
from app import utils, forms
from BillQuery.models import Vote, Choice, ChoiceVote
from USQuery import settings
from django.http import JsonResponse

def home(request):
    """Renders the home page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'BillQuery/index.html',
        {   
            'title':"Bill Query", 
            'content':"Make a bill Query",
            "cong_form": forms.CongressForm,
            "date_form": forms.DateForm(request.GET),
        }
    )

def query(request):
    date_form = forms.DateForm(request.GET)
    return search(request,
                    date_form.data["start_date_day"],
                    date_form.data["start_date_month"],
                    date_form.data["start_date_year"],
                    date_form.data["end_date_day"],
                    date_form.data["end_date_month"],
                    date_form.data["end_date_year"])
    # have to not make response\
    #return HttpResponseRedirect('/bill-query/')

def search(request, s_d, s_m, s_y, e_d, e_m, e_y):
    q_set = utils.getBillsInRange(s_d, s_m, s_y, e_d, e_m, e_y)
    urlPath = ""
    past_context = request.GET.dict()
    for key in past_context:
        urlPath += key + "=" + past_context[key] + "&"
        
    paginator = Paginator(q_set, 25)
    page_number = request.GET.get("page")
    bill_list = paginator.get_page(page_number)
    content = utils.billTable(bill_list)
    return render(
        request,
        'BillQuery/bill_list.html',
        {
            "content": content,
            "bill_list" : bill_list,
            "urlPath" : urlPath,
            'title':"Results",
        }
    )

def bill(request, congress_id, type, num):
    assert isinstance(request, HttpRequest)
    context = utils.billHtml(str(congress_id), type, str(num))
    return render(
        request,
        'BillQuery/bill.html',
        context
    )

def vote(request, vote_id):
    try:
        vote = Vote.objects.get(id = vote_id)
    except Vote.DoesNotExist:
        return HttpResponseRedirect('/bill-query')
    context = utils.voteHtml(vote)
    return render(
        request,
        'BillQuery/vote.html',
        context
    )

@staff_member_required
def populate_bills(request, congress = 116, _type = 's', limit = 100, offset = 0):
    assert isinstance(request, HttpRequest)
    utils.addBills(congress, _type, limit, offset)
    return HttpResponseRedirect("/")