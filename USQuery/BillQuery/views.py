import asyncio
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponseRedirect
from app import utils, forms, siteutils
from BillQuery.models import Vote, Bill, BillPrediction

def home(request):
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'BillQuery/index.html',
        {   
            'title':"Bill Query", 
            "calendar_form" : forms.CalendarDateForm(request.GET),
            "bill_form" : forms.BillForm(request.GET),
            "vote_form" : forms.VoteForm(request.GET)
        }
    )

def query(request):
    assert isinstance(request, HttpRequest)
    cal_form = forms.CalendarDateForm(request.GET)
    return search(request, cal_form.data["start_date"], cal_form.data["end_date"], cal_form.data["bill_type"])

def vote_query(request):
    assert isinstance(request, HttpRequest)
    vote_form = forms.VoteForm(request.GET)
    return vote_search(request, vote_form.data["start_date"], vote_form.data["end_date"], vote_form.data["bill_type"])

def bill_search(request):
    assert isinstance(request, HttpRequest)
    bill_form = forms.BillForm(request.GET)
    return bill(request, bill_form.data["congress"], bill_form.data["bill_type"], bill_form.data["bill_num"])

def search(request, s_d, e_d, bill_type):
    assert isinstance(request, HttpRequest)
    try: 
        q_set = utils.getBillsInRange(s_d, e_d, bill_type)
    except:
        return HttpResponseRedirect('/bill-query')
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

def vote_search(request, s_d, e_d, bill_type):
    assert isinstance(request, HttpRequest)
    try:
        q_set = utils.getVotesInRange(s_d, e_d, bill_type)
    except:
        return HttpResponseRedirect('/bill-query')
    urlPath = ""
    past_context = request.GET.dict()
    for key in past_context:
        urlPath += key + "=" + past_context[key] + "&"
        
    paginator = Paginator(q_set, 25)
    page_number = request.GET.get("page")
    vote_list = paginator.get_page(page_number)
    content = utils.voteTablePage(vote_list)
    return render(
        request,
        'BillQuery/bill_list.html',
        {
            "content": content,
            "bill_list" : vote_list,
            "urlPath" : urlPath,
            'title':"Results",
        }
    )

def bill(request, congress_num, bill_type, bill_num):
    assert isinstance(request, HttpRequest)
    mult = 10 if int(bill_num) > 9999 else 1
    # CCC_T_XXXX(X)
    bill_id = (int(congress_num) * 1_0_0000 * mult) + (utils.types[bill_type] * 1_0000 * mult) + int(bill_num)
    try:
        bill = Bill.objects.get(id = bill_id)
    except Bill.DoesNotExist:
        return HttpResponseRedirect('/bill-query')
    context = asyncio.run(utils.billHtml(str(congress_num), bill_type, str(bill_num)))
    context['bill_id'] = bill_id
    context['bill_type'] = bill_type
    context['show_prediction'] = False
    context['show_request_button'] = False
    context['show_error'] = False
    ## if logged in + bill eligible for prediction get simulated votes
    logged_in = (request.user.is_authenticated) and (not bill.status) and (congress_num >= 119)
    pred_exists = BillPrediction.objects.filter(id = bill_id).exists()
    if pred_exists:
        batch_size = 100
        context['house_pred'] = siteutils.getPredictionBatch(bill_id, True, batch_size)
        context['senate_pred'] = siteutils.getPredictionBatch(bill_id, False, batch_size)
        if context['house_pred'] == -1 or context['senate_pred'] == -1:
            context['show_error'] = True
        else: 
             context['show_prediction'] = True
    elif logged_in:
        context['show_request_button'] = True
        context['request_link'] = "/bill-query/prediction-request/" + str(congress_num) + "/" + bill_type + "/" + str(bill_num)
    return render(
        request,
        'BillQuery/bill.html',
        context
    )

@login_required
def requestPrediction(request, congress_num, bill_type, bill_num):
    assert isinstance(request, HttpRequest)
    if congress_num >= 119:
        mult = 10 if int(bill_num) > 9999 else 1
        bill_id = (int(congress_num) * 1_0_0000 * mult) + (utils.types[bill_type] * 1_0000 * mult) + int(bill_num)
        try:
            Bill.objects.get(id = bill_id)
        except Bill.DoesNotExist:
            return HttpResponseRedirect('/bill-query')
        siteutils.getPredictionBatch(bill_id, True, 0, False)
    return HttpResponseRedirect("/bill-query/bill/" + str(congress_num) + "/" + bill_type + "/" + str(bill_num))

def vote(request, vote_id):
    assert isinstance(request, HttpRequest)
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
def populate_bills(request, congress_num, bill_type, limit, offset):
    assert isinstance(request, HttpRequest)
    asyncio.run(utils.addBills(congress_num, bill_type, limit, offset))
    return HttpResponseRedirect("/bill-query")

@staff_member_required
def update_bill(request, congress_num, bill_type, bill_num):
    assert isinstance(request, HttpRequest)
    asyncio.run(utils.updateBill(congress_num, bill_type, bill_num))
    return HttpResponseRedirect("/bill-query/bill/" + str(congress_num) + "/" + bill_type + "/" + str(bill_num))

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