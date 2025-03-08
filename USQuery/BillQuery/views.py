import asyncio
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
            "calendar_form" : forms.CalendarDateForm(request.GET)
        }
    )

def query(request):
    cal_form = forms.CalendarDateForm(request.GET)
    return search(request, cal_form.data["start_date"], cal_form.data["end_date"])

def search(request, s_d, e_d):
    q_set = utils.getBillsInRange(s_d, e_d)
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
    context = asyncio.run(utils.billHtml(str(congress_id), type, str(num)))
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
    context['cloro_form'] = forms.CloroChoice(request.GET)
    return render(
        request,
        'BillQuery/vote.html',
        context
    )

@staff_member_required
def populate_bills(request, congress = 116, _type = 's', limit = 100, offset = 0):
    assert isinstance(request, HttpRequest)
    asyncio.run(utils.addBills(congress, _type, limit, offset))
    return HttpResponseRedirect("/bill-query")

@staff_member_required
def update_bill(request, congress, _type, _num):
    assert isinstance(request, HttpRequest)
    asyncio.run(utils.updateBill(congress, _type, _num))
    return HttpResponseRedirect("/bill-query/results/bill/" + str(congress) + "/" + _type + "/" + str(_num))

@staff_member_required
def fix_votes(request, congress_num, year, nums):
    member_ids = request.GET['member_ids'].split(',')
    assert isinstance(request, HttpRequest)
    asyncio.run(utils.fixHouseVotes(congress_num, year, nums, member_ids))
    return HttpResponseRedirect("/bill-query")

@staff_member_required
def update_votes(request, congress_num, date):
    assert isinstance(request, HttpRequest)
    for t in utils.types :
        asyncio.run(utils.updateRecentBills(congress_num, date, t))
    return HttpResponseRedirect("/bill-query")