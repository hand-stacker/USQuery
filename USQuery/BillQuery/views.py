import asyncio
import os
import aiohttp
from django.shortcuts import render
from django.db.models import Q
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.cache import cache
from django.http import HttpRequest, HttpResponseRedirect, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from app import utils, forms, siteutils
from SenateQuery.models import Congress
from BillQuery.models import Vote, Bill, BillPrediction
from datetime import date
from app.models import UserProfile
from notifications.push import send_subject_notification


def home(request):
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'BillQuery/index.html',
        {   
            'title':"Bill Query", 
            "bill_form" : forms.BillForm(request.GET),
            "vote_form" : forms.VoteForm(request.GET)
        }
    )

def bill_query(request):
    assert isinstance(request, HttpRequest)
    bill_form = forms.BillForm(request.GET)
    # Use QueryDict.getlist to preserve all selected values from a multi-select input
    raw_subject_ids = request.GET.get("bill_subjects", '')
    if raw_subject_ids == '':
        topics=[]
    else : 
        topics = list(map(int, raw_subject_ids.split(',')))
    return bill_search(
        request,
        bill_form.data.get("start_date"),
        bill_form.data.get("end_date"),
        bill_form.data.get("bill_type"),
        topics
    )

def vote_query(request):
    assert isinstance(request, HttpRequest)
    vote_form = forms.VoteForm(request.GET)
    # VoteForm uses the same field name 'bill_subjects' — use getlist here as well
    raw_subject_ids = request.GET.get("vote_subjects", '')
    if raw_subject_ids == '':
        topics=[]
    else : 
        topics = list(map(int, raw_subject_ids.split(',')))
    raw_subject_ids = list(map(int, raw_subject_ids))
    return vote_search(
        request,
        vote_form.data.get("start_date"),
        vote_form.data.get("end_date"),
        vote_form.data.get("bill_type"),
        topics
    )

def bill_search(request, s_d, e_d, bill_type, topics):
    assert isinstance(request, HttpRequest)
    try: 
        q_set = utils.getBillsInRange(s_d, e_d, bill_type, topics)
    except:
        return render(request, 'BillQuery/search_failed.html', {
            'title': 'Search failed',
            'return_url': '/bill-query/'
        })
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

def vote_search(request, s_d, e_d, bill_type, topics):
    assert isinstance(request, HttpRequest)
    try:
        q_set = utils.getVotesInRange(s_d, e_d, bill_type, topics)
    except:
        return render(request, 'BillQuery/search_failed.html', {
            'title': 'Search failed',
            'return_url': '/bill-query/'
        })
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

def search_failed(request):
    """
    Simple view to render the search_failed template.
    """
    assert isinstance(request, HttpRequest)
    return render(request, 'BillQuery/search_failed.html', {
        'title': 'Search failed',
        'return_url': '/bill-query/'
    })

def bill(request, congress_num, bill_type, bill_num, _bill = None, bill_id = None):
    assert isinstance(request, HttpRequest)
    if _bill == None:
        mult = 10 if int(bill_num) > 9999 else 1
        # CCC_T_XXXX(X)
        bill_id = (int(congress_num) * 1_0_0000 * mult) + (utils.types[bill_type] * 1_0000 * mult) + int(bill_num)
        try:
            _bill = Bill.objects.get(id = bill_id)
        except Bill.DoesNotExist:
            return render(request, 'BillQuery/search_failed.html', {
                'title': 'Bill does not exist',
                'return_url': '/bill-query/'
            })
    context = asyncio.run(utils.billHtml(_bill, str(congress_num), bill_type, str(bill_num)))
    context['isStarred'] = False
    context['loggedIn'] = False
    if request.user.is_authenticated:
        context['loggedIn'] = True
        user_profile = UserProfile.objects.get(user=request.user)
        sb_qs = user_profile.get_starred_bills()
        raw_ids = list(sb_qs.values_list("bill_id", flat=True))
        if str(bill_id) in raw_ids:
            context['isStarred'] = True
    context['bill_id'] = bill_id
    context['bill_type'] = bill_type
    context['congress_num'] = congress_num
    context['bill_num'] = bill_num
    context['show_prediction'] = False
    context['show_request_button'] = False
    context['show_error'] = False
    context['eligible_for_prediction'] = (not _bill.status) and (congress_num >= 119)
    pred_exists = BillPrediction.objects.filter(id = bill_id).exists()
    if pred_exists:
        batch_size = 1000
        context['house_pred'] = siteutils.getPredictionBatch(bill_id, True, batch_size)
        context['senate_pred'] = siteutils.getPredictionBatch(bill_id, False, batch_size)
        if context['house_pred'] == -1 or context['senate_pred'] == -1:
            context['show_error'] = True
        else: 
             context['show_prediction'] = True
    else:
        context['show_request_button'] = True
        context['request_link'] = "/bill-query/prediction-request/" + str(congress_num) + "/" + bill_type + "/" + str(bill_num)
    return render(
        request,
        'BillQuery/bill.html',
        context
    )

def requestPrediction(request, congress_num, bill_type, bill_num):
    assert isinstance(request, HttpRequest)
    if congress_num >= 119:
        mult = 10 if int(bill_num) > 9999 else 1
        bill_id = (int(congress_num) * 1_0_0000 * mult) + (utils.types[bill_type] * 1_0000 * mult) + int(bill_num)
        try:
            Bill.objects.get(id = bill_id)
        except Bill.DoesNotExist:
            return render(request, 'BillQuery/search_failed.html', {
                'title': 'Bill does not exist',
                'return_url': '/bill-query/'
            })
        siteutils.getPredictionBatch(bill_id, True, 0, False)
    return HttpResponseRedirect("/bill-query/bill/" + str(congress_num) + "/" + bill_type + "/" + str(bill_num))

def vote(request, vote_id):
    assert isinstance(request, HttpRequest)
    try:
        vote = Vote.objects.get(id = vote_id)
    except Vote.DoesNotExist:
        return render(request, 'BillQuery/search_failed.html', {
                'title': 'Vote does not exist',
                'return_url': '/bill-query/'
            })
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
    subjects = cache.get("bill_subjects", set())
    asyncio.run(send_subject_notification(
        subjects=subjects,
        title="New actions on bills you might be interested in.",
        body="New actions were made on bills related to your favorite subjects."
    ))
    cache.delete("bill_subjects")
    return HttpResponseRedirect("/bill-query")

def daily_task(request):
    secret = request.GET["X-TASK-SECRET"]
    if secret != os.environ.get("TASK_SECRET"):
        return HttpResponseForbidden("Forbidden")
    for t in utils.types :
        asyncio.run(utils.updateRecentBills(119, "!", t))
    return JsonResponse({"status": "ok"})

# AJAX/POST endpoint that generates an AI summary for a bill on-demand.
# The front-end should POST to this endpoint (CSRF-protected). Returns JSON
# { 'status': 'ok', 'summary': '<html...>' } on success.

@login_required
@require_POST
def generate_summary(request, congress_num, bill_type, bill_num):
    
    assert isinstance(request, HttpRequest)
    # Compute bill id same way as used in other views
    mult = 10 if int(bill_num) > 9999 else 1
    bill_id = (int(congress_num) * 1_0_0000 * mult) + (utils.types[bill_type] * 1_0000 * mult) + int(bill_num)

    # verify bill exists
    try:
        Bill.objects.get(id=bill_id)
    except Bill.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Bill not found'}, status=404)
    apiURL = settings.CONGRESS_DIR + "bill/" + str(congress_num) + "/" + bill_type + "/" + str(bill_num)
    header_str = '?api_key=' + settings.CONGRESS_KEY +  '&format=json&limit=250'

    async def _generate():
        session = aiohttp.ClientSession()
        try:
            summary = await utils.getSummaryAI(session, apiURL + "/text", header_str, bill_id)
            return summary
        finally:
            await session.close()

    try:
        summary = asyncio.run(_generate())
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Generation failed: {e}'}, status=500)

    return JsonResponse({'status': 'ok', 'summary': summary})