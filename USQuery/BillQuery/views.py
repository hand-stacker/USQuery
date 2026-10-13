import asyncio
import hashlib
import json
import uuid as uuid_lib
from urllib.parse import quote_plus
import aiohttp
import anthropic
from collections import Counter
from django.shortcuts import render
from django.db.models import Q, Prefetch, Sum, F
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.cache import cache
from django.http import HttpRequest, HttpResponseRedirect, HttpResponseForbidden, HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.conf import settings
from asgiref.sync import sync_to_async
from app import utils, forms, siteutils
from SenateQuery.models import Congress, Membership
from BillQuery.models import Vote, Bill, BillPrediction, BillSummary, Subject, BinaryProbability, US_EASTERN
from datetime import date
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response as DRFResponse
from app.models import UserProfile, ChatSession, ChatMessage, BillChunk, ApiUsageEvent, OUTPUT_TOKEN_COST_WEIGHT
from app.rag import index_bill, retrieve_relevant_chunks
from app.usage_tracking import alog_usage
from notifications.push import send_subject_notification
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramWordSimilarity
from django.db.models import F, Q, Count, Prefetch, Value, FloatField, Subquery, OuterRef
from BillQuery.bill_reference import bill_reference_candidate_ids, parse_bill_reference
from django.db.models.functions import Coalesce, Greatest

def home(request):
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'BillQuery/index.html',
        {
            'title':"Bill Query",
            "bill_keyword_form" : forms.BillKeywordForm(request.GET),
            "bill_form" : forms.BillForm(request.GET)
        }
    )

def vote_home(request):
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'BillQuery/vote_index.html',
        {
            'title':"Vote Query",
            "vote_keyword_form" : forms.VoteKeywordForm(request.GET),
            "vote_form" : forms.VoteForm(request.GET)
        }
    )

def _parse_subject_ids(raw):
    """Comma-separated numeric subject ids -> list of ints; None if anything else."""
    if raw == '':
        return []
    parts = raw.split(',')
    if not all(p.strip().isdigit() for p in parts):
        return None
    return [int(p) for p in parts]

def bill_query(request):
    assert isinstance(request, HttpRequest)
    bill_form = forms.BillForm(request.GET)
    # Use QueryDict.getlist to preserve all selected values from a multi-select input
    topics = _parse_subject_ids(request.GET.get("bill_subjects", ''))
    if topics is None:
        return HttpResponseBadRequest("bill_subjects must be comma-separated numeric ids.")
    s_d = bill_form.data.get("start_date")
    e_d = bill_form.data.get("end_date")
    if _dates_out_of_order(s_d, e_d):
        return _search_failed(
            request, '/bill/', "End date cannot be earlier than the start date."
        )
    return bill_search(
        request,
        s_d,
        e_d,
        bill_form.data.get("bill_type"),
        topics
    )

def vote_query(request):
    assert isinstance(request, HttpRequest)
    vote_form = forms.VoteForm(request.GET)
    # VoteForm uses the same field name 'bill_subjects' - use getlist here as well
    topics = _parse_subject_ids(request.GET.get("vote_subjects", ''))
    if topics is None:
        return HttpResponseBadRequest("vote_subjects must be comma-separated numeric ids.")
    s_d = vote_form.data.get("start_date")
    e_d = vote_form.data.get("end_date")
    if _dates_out_of_order(s_d, e_d):
        return _search_failed(
            request, '/vote/', "End date cannot be earlier than the start date."
        )
    return vote_search(
        request,
        s_d,
        e_d,
        vote_form.data.get("bill_type"),
        topics
    )

def bill_keyword_query(request):
    assert isinstance(request, HttpRequest)
    bill_form = forms.BillKeywordForm(request.GET)
    if not bill_form.is_valid():
        return _search_failed(request, '/bill/', _form_error_message(bill_form))
    keyword = str(bill_form.cleaned_data.get("bill_keyword") or '').strip()
    bill_type = bill_form.cleaned_data.get("bill_type") or '!'
    sort = bill_form.cleaned_data.get("sorttype")
    s_d, e_d = _resolve_date_window(
        _as_iso(bill_form.cleaned_data.get("start_date")),
        _as_iso(bill_form.cleaned_data.get("end_date")),
    )
    # An empty keyword would hand SearchQuery('') and the trigram operators nothing to
    # match on, so fall through to the plain date-range search instead.
    if not keyword:
        return bill_search(request, s_d, e_d, bill_type, [])
    return bills_by_keyword(request, keyword, s_d, e_d, bill_type, sort)

def vote_keyword_query(request):
    assert isinstance(request, HttpRequest)
    vote_form = forms.VoteKeywordForm(request.GET)
    if not vote_form.is_valid():
        return _search_failed(request, '/vote/', _form_error_message(vote_form))
    keyword = str(vote_form.cleaned_data.get("vote_keyword") or '').strip()
    bill_type = vote_form.cleaned_data.get("bill_type") or '!'
    sort = vote_form.cleaned_data.get("sorttype")
    s_d, e_d = _resolve_date_window(
        _as_iso(vote_form.cleaned_data.get("start_date")),
        _as_iso(vote_form.cleaned_data.get("end_date")),
    )
    if not keyword:
        return vote_search(request, s_d, e_d, bill_type, [])
    return votes_by_keyword(request, keyword, s_d, e_d, bill_type, sort)

def _search_failed(request, return_url, message=None):
    """Render the search-failed page, optionally explaining what went wrong."""
    return render(request, 'BillQuery/search_failed.html', {
        'title': 'Search failed',
        'return_url': return_url,
        'error_message': message,
    })

def _form_error_message(form):
    """Flatten a bound form errors into one sentence for the failure page."""
    return " ".join(msg for errors in form.errors.values() for msg in errors)

def _dates_out_of_order(s_d, e_d):
    """True when both dates are given and the range runs backwards.

    The range forms cannot be run through full form validation - their subjects
    field arrives as one comma-joined string rather than a list - so they get this
    direct check instead. ISO YYYY-MM-DD sorts correctly as a string, so nothing
    needs parsing; anything malformed compares harmlessly and is caught downstream
    by getBillsInRange.
    """
    return bool(s_d) and bool(e_d) and str(s_d) > str(e_d)

def _as_iso(value):
    """A cleaned DateField value back as a YYYY-MM-DD string, or None if blank."""
    return value.strftime('%Y-%m-%d') if value else None

def _resolve_date_window(s_d, e_d):
    """Fill in either date the user left blank from the Congress sitting today.

    Both fields are optional on the keyword forms, so an unbounded search means
    "this Congress" rather than "all of history". Resolved here rather than
    downstream so the dates reach url_params too and survive pagination.
    """
    if s_d and e_d:
        return s_d, e_d
    ## Congresses convene on Jan 3 of an odd year and hand over two years later, so
    ## the window is arithmetic on today's date - no Congress row lookup, which would
    ## add a query per search and turn a database hiccup into a failed search.
    today = date.today()
    start_year = today.year if today.year % 2 else today.year - 1
    start, end = date(start_year, 1, 3), date(start_year + 2, 1, 3)
    return (s_d or start.strftime('%Y-%m-%d'), e_d or end.strftime('%Y-%m-%d'))

def _congress_nums_in_range(s_d, e_d):
    """Congress numbers whose sessions overlap the given YYYY-MM-DD window, newest first."""
    start_year = int(str(s_d).split('-')[0])
    end_year = int(str(e_d).split('-')[0])
    # A congress that ends in year N still collects actions into early N+1, which is why
    # the tail boundary is compared against start_year - 1.
    nums = list(
        Congress.objects
        .filter(start_year__lte=end_year)
        .filter(Q(end_year__isnull=True) | Q(end_year__gte=start_year - 1))
        .order_by("-congress_num")
        .values_list("congress_num", flat=True)
    )
    return nums or [_current_congress()]

def _paginate_ranked_ids(request, ranked_ids, per_page):
    """Paginate an already-ranked id list. Returns (page_obj, ids on this page)."""
    paginator = Paginator(ranked_ids, per_page)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except:
        page_obj = paginator.page(1)
    return page_obj, list(page_obj.object_list)

def bill_search(request, s_d, e_d, bill_type, topics):
    assert isinstance(request, HttpRequest)
    try: 
        q_set = utils.getBillsInRange(s_d, e_d, bill_type, topics)
    except:
        return render(request, 'BillQuery/search_failed.html', {
            'title': 'Search failed',
            'return_url': '/bill/'
        })
    
    # Convert topics list to JSON for frontend
    selected_subjects_json = []
    if topics:
        selected_subjects = Subject.objects.filter(id__in=topics)
        selected_subjects_json = [{"id": s.id, "name": s.name} for s in selected_subjects]
    
    # Server-side pagination: 50 bills per page to keep JSON size manageable
    BILLS_PER_PAGE = 50
    paginator = Paginator(q_set, BILLS_PER_PAGE)
    page_number = request.GET.get("page", 1)
    
    try:
        page_obj = paginator.page(page_number)
    except:
        page_obj = paginator.page(1)
    
    # Serialize bills data for current page only
    bills_data = []
    for bill in page_obj:
        bill_subjects = []
        if topics:
            # Get only subjects that match the selected filters
            bill_subjects = [{"id": s.id, "name": s.name} for s in bill.subjects.filter(id__in=topics)]
        
        bills_data.append({
            "bill_id": bill.id,
            "title": bill.title,
            "latest_action": bill.latest_action.isoformat() if bill.latest_action else None,
            "subjects": bill_subjects
        })
    
    # Construct URL parameters for pagination links
    url_params = ""
    if s_d:
        url_params += f"start_date={s_d}&"
    if e_d:
        url_params += f"end_date={e_d}&"
    if bill_type:
        url_params += f"bill_type={bill_type}&"
    if topics:
        url_params += f"bill_subjects={','.join(map(str, topics))}&"
    
    return render(
        request,
        'BillQuery/bill_search_results.html',
        {
            "bills_json": bills_data,
            "selected_subjects_json": selected_subjects_json,
            "page_obj": page_obj,
            "url_params": url_params,
            'title': "Results",
        }
    )

def bills_by_keyword(request, keyword, s_d, e_d, bill_type, sort):
    return bill_search(request, s_d, e_d, bill_type, [])

def vote_search(request, s_d, e_d, bill_type, topics):
    assert isinstance(request, HttpRequest)
    try:
        q_set = utils.getVotesInRange(s_d, e_d, bill_type, topics)
    except:
        return render(request, 'BillQuery/search_failed.html', {
            'title': 'Search failed',
            'return_url': '/vote/'
        })
    
    # Convert topics list to JSON for frontend
    selected_subjects_json = []
    if topics:
        selected_subjects = Subject.objects.filter(id__in=topics)
        selected_subjects_json = [{"id": s.id, "name": s.name} for s in selected_subjects]
    
    # Server-side pagination: 50 votes per page to keep JSON size manageable
    VOTES_PER_PAGE = 50
    paginator = Paginator(q_set, VOTES_PER_PAGE)
    page_number = request.GET.get("page", 1)
    
    try:
        page_obj = paginator.page(page_number)
    except:
        page_obj = paginator.page(1)
    
    # Prefetch related bills and their subjects in bulk to avoid N+1 queries
    votes_with_bills = list(page_obj.object_list)
    
    if votes_with_bills:
        bill_ids = [v.bill_id for v in votes_with_bills if v.bill_id]
        
        # Prefetch bills with their subjects in one query
        bills_with_subjects = Bill.objects.filter(
            id__in=bill_ids
        ).prefetch_related(
            Prefetch(
                'subjects',
                queryset=Subject.objects.filter(id__in=topics) if topics else Subject.objects.all()
            )
        )
        
        # Create a map for quick lookup
        bills_map = {bill.id: bill for bill in bills_with_subjects}
        
        # Serialize votes data for current page only
        votes_data = []
        for vote in votes_with_bills:
            bill = bills_map.get(vote.bill_id) if vote.bill_id else None
            
            vote_subjects = []
            if topics and bill:
                vote_subjects = [{"id": s.id, "name": s.name} for s in bill.subjects.all()]
            
            votes_data.append({
                "vote_id": vote.id,
                "date": vote.localDateTime().isoformat() if vote.dateTime else None,
                "question": vote.question,
                "result": vote.result,
                "bill_id": bill.id if bill else None,
                "bill_title": bill.title if bill else "Unknown Bill",
                "bill_type_url": bill.getTypeURL() if bill else "",
                "bill_number": bill.getNumStr() if bill else "",
                "subjects": vote_subjects
            })
    else:
        votes_data = []
    
    # Construct URL parameters for pagination links
    url_params = ""
    if s_d:
        url_params += f"start_date={s_d}&"
    if e_d:
        url_params += f"end_date={e_d}&"
    if bill_type:
        url_params += f"bill_type={bill_type}&"
    if topics:
        url_params += f"vote_subjects={','.join(map(str, topics))}&"
    
    return render(
        request,
        'BillQuery/vote_search_results.html',
        {
            "votes_json": votes_data,
            "selected_subjects_json": selected_subjects_json,
            "page_obj": page_obj,
            "url_params": url_params,
            'title': "Results",
        }
    )

def votes_by_keyword(request, keyword, s_d, e_d, bill_type, sort):
    return vote_search(request, s_d, e_d, bill_type, [])

def search_failed(request):
    """
    Simple view to render the search_failed template.
    """
    assert isinstance(request, HttpRequest)
    return render(request, 'BillQuery/search_failed.html', {
        'title': 'Search failed',
        'return_url': '/bill/'
    })

_BILL_TYPE_DISPLAY = {
    'hr': 'H.R.', 's': 'S.', 'hjres': 'H.J.Res.', 'sjres': 'S.J.Res.',
    'hconres': 'H.Con.Res.', 'sconres': 'S.Con.Res.', 'hres': 'H.Res.', 'sres': 'S.Res.'
}

def _current_congress():
    """Return the current Congress number based on today's date."""
    return (date.today().year - 1787) // 2

def _list_to_dist(pred_list):
    """Convert list of sampled vote totals to {str(count): frequency} dict."""
    return {str(k): v for k, v in sorted(Counter(pred_list).items())}

def _build_member_predictions(bill_pred):
    """Return (house_members, senate_members) with per-member probabilities."""
    today = date.today().strftime('%Y-%m-%d')
    query = (
        (Q(end_date=None) | Q(end_date__gte=today)) &
        Q(congress__congress_num=_current_congress())
    )
    memberships = (Membership.objects.filter(query).select_related('member'))

    probs = {
        (bp.state, bp.in_house, bp.party): float(bp.p)
        for bp in BinaryProbability.objects.filter(bill_pred=bill_pred)
    }

    house_members, senate_members = [], []
    for m in memberships:
        key = (m.state, m.house, m.party)
        prob = probs.get(key, 0.5)
        party_abbr = 'D' if m.party.startswith('D') else ('R' if m.party.startswith('R') else 'I')
        entry = {
            'name': m.member.full_name,
            'party': party_abbr,
            'state': m.state,
            'district': m.district_num,
            'prob': round(prob, 4),
        }
        if m.house:
            house_members.append(entry)
        else:
            senate_members.append(entry)

    house_members.sort(key=lambda x: x['prob'], reverse=True)
    senate_members.sort(key=lambda x: x['prob'], reverse=True)
    return house_members, senate_members


## Prediction access by tier. Tier ids don't sort by plan level (Plus Pro is 4,
## Premium is 2), so never compare user_type numerically -- go through the
## profile's DAILY_PREDICTION_CREDITS allowance instead:
##   0 -> no access, >= _UNLIMITED_PRED_CREDITS -> unlimited, else metered daily.
_UNLIMITED_PRED_CREDITS = 10000

def _pred_access(user_profile):
    """('none' | 'metered' | 'unlimited', daily credit limit)."""
    limit = user_profile.get_daily_prediction_credits()
    if limit <= 0:
        return 'none', 0
    if limit >= _UNLIMITED_PRED_CREDITS:
        return 'unlimited', limit
    return 'metered', limit

def _pred_today():
    """Credit-day key. The UI promises a reset at midnight ET, not server (UTC) midnight."""
    return timezone.localdate(timezone=US_EASTERN).isoformat()

## get and iter funcs for metered (Plus / Plus Pro) prediction credits
def _get_pred_credits_remaining(user_id, today, limit):
    used = cache.get(f'pred_credits_used:{user_id}:{today}', 0)
    return max(0, limit - used)

def _spend_pred_credit(user_id, today, limit):
    used = cache.get(f'pred_credits_used:{user_id}:{today}', 0)
    cache.set(f'pred_credits_used:{user_id}:{today}', used + 1, timeout=86400)
    return max(0, limit - used - 1)

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
                'return_url': '/bill/'
            })
    try:
        context = asyncio.run(utils.billHtml(_bill, str(congress_num), bill_type, str(bill_num)))
    except utils.BillUpstreamUnavailable:
        # Congress API is slow/down; render a friendly retry page rather than a 500.
        return render(request, 'BillQuery/search_failed.html', {
            'title': 'Bill temporarily unavailable',
            'error_message': 'We could not load this bill right now (data provider is slow). Please try again in a moment.',
            'return_url': '/bill/'
        }, status=503)
    context['isStarred'] = False
    context['loggedIn'] = False
    context['chat_enabled'] = False
    context['show_login_for_summary'] = False
    if not request.user.is_authenticated and context.get('show_generate_button'):
        context['show_generate_button'] = False
        context['show_login_for_summary'] = True
    if request.user.is_authenticated:
        context['loggedIn'] = True
        user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
        context['chat_enabled'] = user_profile.get_chat_limit() > 0
        sb_qs = user_profile.get_starred_bills()
        raw_ids = list(sb_qs.values_list("bill_id", flat=True))
        if str(bill_id) in raw_ids:
            context['isStarred'] = True
    context['bill_id'] = bill_id
    context['bill_type'] = bill_type
    context['congress_num'] = congress_num
    context['bill_num'] = bill_num
    context['eligible_for_prediction'] = (not _bill.status) and (congress_num == _current_congress())

    if context['eligible_for_prediction']:
        today = _pred_today()
        # The front end knows four UI modes; 'plus' is the metered one (Plus and
        # Plus Pro), 'premium' the unlimited one (Premium and Special).
        vp_credits = None
        vp_credit_limit = None
        if not request.user.is_authenticated:
            vp_tier = 'guest'
        else:
            access, limit = _pred_access(user_profile)
            if access == 'none':
                vp_tier = 'free'
            elif access == 'metered':
                vp_tier = 'plus'
                vp_credit_limit = limit
                vp_credits = _get_pred_credits_remaining(request.user.id, today, limit)
            else:
                vp_tier = 'premium'

        pred_exists = BillPrediction.objects.filter(id=bill_id).exists()

        if pred_exists:
            try:
                house_pred = siteutils.getPredictionBatch(bill_id, True, 10000)
                senate_pred = siteutils.getPredictionBatch(bill_id, False, 10000)
            except siteutils.PredictionDataError:
                house_pred = None
                senate_pred = None
            if (house_pred is not None and house_pred != -1 and
                    senate_pred is not None and senate_pred != -1):
                vp_pred_state = 'ready'
                vp_house_dist = _list_to_dist(house_pred)
                vp_senate_dist = _list_to_dist(senate_pred)
            else:
                vp_pred_state = 'error'
                vp_house_dist = None
                vp_senate_dist = None
        else:
            vp_pred_state = 'empty'
            vp_house_dist = None
            vp_senate_dist = None

        if vp_tier == 'premium':
            vp_member_unlocked = pred_exists
        elif vp_tier == 'plus' and pred_exists:
            vp_member_unlocked = bool(cache.get(f'pred_member_reveal:{request.user.id}:{bill_id}'))
        else:
            vp_member_unlocked = False

        context.update({
            'vp_pred_state': vp_pred_state,
            'vp_user_tier': vp_tier,
            'vp_pred_credits': vp_credits,
            'vp_pred_credit_limit': vp_credit_limit,
            'vp_member_unlocked': vp_member_unlocked,
            'vp_house_dist': vp_house_dist,
            'vp_senate_dist': vp_senate_dist,
            'vp_bill_display': f"{_BILL_TYPE_DISPLAY.get(bill_type.lower(), bill_type.upper())} {bill_num} · {congress_num}th",
        })

    return render(
        request,
        'BillQuery/bill.html',
        context
    )

## Staff-only: it runs the paid prediction pipeline with no tier checks, and no
## page links to it (users go through generate_prediction_ajax).
@staff_member_required
def requestPrediction(request, congress_num, bill_type, bill_num):
    assert isinstance(request, HttpRequest)
    mult = 10 if int(bill_num) > 9999 else 1
    bill_id = (int(congress_num) * 1_0_0000 * mult) + (utils.types[bill_type] * 1_0000 * mult) + int(bill_num)
    try:
        bill_obj = Bill.objects.get(id = bill_id)
    except Bill.DoesNotExist:
        return render(request, 'BillQuery/search_failed.html', {
            'title': 'Bill does not exist',
            'return_url': '/bill/'
        })
    if congress_num != _current_congress() or bill_obj.status:
        return HttpResponseForbidden("Predictions are only available for open bills in the current Congress.")
    try:
        siteutils.getPredictionBatch(bill_id, True, 0, False)
    except siteutils.PredictionDataError:
        pass
    return HttpResponseRedirect("/bill/" + str(congress_num) + "/" + bill_type + "/" + str(bill_num))


@api_view(['POST'])
@authentication_classes([SessionAuthentication, JWTAuthentication])
@permission_classes([AllowAny])
def generate_prediction_ajax(request, bill_id):
    """AJAX: Fetch or generate a vote prediction for a bill.

    ?generate=false  — read-only, no auth required, returns exists flag + dist if available.
    ?generate=true   — (default) generate via ML model, requires Plus/Premium auth.
    """
    should_generate = request.query_params.get('generate', 'true').lower() != 'false'

    if not should_generate:
        try:
            Bill.objects.get(id=bill_id)
        except Bill.DoesNotExist:
            return JsonResponse({'error': 'bill_not_found'}, status=404)

        if not BillPrediction.objects.filter(id=bill_id).exists():
            return JsonResponse({'exists': False})

        try:
            house_pred = siteutils.getPredictionBatch(bill_id, True, 10000)
            senate_pred = siteutils.getPredictionBatch(bill_id, False, 10000)
        except siteutils.PredictionDataError as e:
            return JsonResponse({'exists': True, 'error': 'prediction_unavailable',
                                 'reason': e.reason, 'detail': e.detail}, status=422)
        if house_pred is None or house_pred == -1 or senate_pred is None or senate_pred == -1:
            return JsonResponse({'exists': True, 'error': 'data_unavailable'})

        response = {
            'exists': True,
            'house_dist': _list_to_dist(house_pred),
            'senate_dist': _list_to_dist(senate_pred),
        }

        if request.user.is_authenticated:
            up, _ = UserProfile.objects.get_or_create(user=request.user)
            access, limit = _pred_access(up)
            today = _pred_today()
            if access == 'metered':
                response['credits_remaining'] = _get_pred_credits_remaining(request.user.id, today, limit)
                response['member_reveal_unlocked'] = bool(cache.get(f'pred_member_reveal:{request.user.id}:{bill_id}'))
            elif access == 'unlimited':
                response['credits_remaining'] = None
                response['member_reveal_unlocked'] = True
            else:
                response['credits_remaining'] = None
                response['member_reveal_unlocked'] = False

        return JsonResponse(response)

    # generate=true — requires authenticated Plus/Premium user
    user = request.user
    if not user.is_authenticated:
        return JsonResponse({'error': 'authentication_required'}, status=401)

    up, _ = UserProfile.objects.get_or_create(user=user)
    access, limit = _pred_access(up)
    today = _pred_today()

    if access == 'none':
        return JsonResponse({'error': 'upgrade_required'}, status=403)

    try:
        bill_obj = Bill.objects.get(id=bill_id)
    except Bill.DoesNotExist:
        return JsonResponse({'error': 'bill_not_found'}, status=404)

    if bill_obj.status:
        return JsonResponse({'error': 'bill_passed'}, status=400)

    _cn = bill_id // 100000
    congress_num = bill_id // 1000000 if _cn > 999 else _cn
    if congress_num != _current_congress():
        return JsonResponse({'error': 'not_eligible'}, status=400)

    if access == 'metered':
        remaining = _get_pred_credits_remaining(user.id, today, limit)
        if remaining <= 0:
            return JsonResponse({'error': 'daily_limit', 'credits_remaining': 0})

    try:
        ## Generate once, then sample both chambers off that single BillPrediction.
        ## Sampling twice used to run generation twice whenever the first attempt
        ## failed, and since the model reply is not deterministic the second could
        ## succeed - writing the prediction while still reporting failure to the
        ## caller, which is why a reload would then show a prediction that had just
        ## "failed" to generate.
        siteutils.getPredictionBatch(bill_id, True, 0, False)
        if not BillPrediction.objects.filter(id=bill_id).exists():
            return JsonResponse({'error': 'generation_failed'}, status=422)
        house_pred = siteutils.getPredictionBatch(bill_id, True, 10000)
        senate_pred = siteutils.getPredictionBatch(bill_id, False, 10000)
    except siteutils.PredictionDataError as e:
        return JsonResponse({'error': 'prediction_unavailable', 'reason': e.reason, 'detail': e.detail}, status=422)

    if house_pred is None or house_pred == -1 or senate_pred is None or senate_pred == -1:
        ## 422, not 500: failing to predict a particular bill is an outcome for that
        ## bill, not a server fault, and burying it among real 500s hides both.
        return JsonResponse({'error': 'generation_failed'}, status=422)

    credits_remaining = None
    if access == 'metered':
        credits_remaining = _spend_pred_credit(user.id, today, limit)
        cache.set(f'pred_member_reveal:{user.id}:{bill_id}', True, timeout=86400)

    return JsonResponse({
        'success': True,
        'house_dist': _list_to_dist(house_pred),
        'senate_dist': _list_to_dist(senate_pred),
        'credits_remaining': credits_remaining,
        'member_reveal_unlocked': True,
    })


@api_view(['POST'])
@authentication_classes([SessionAuthentication, JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_member_predictions(request, bill_id):
    """AJAX: Return per-member vote probabilities (gated by tier and cache).

    ?generate=false  — read-only; returns data only if prediction exists and user has access.
    ?generate=true   — (default) spend a credit if needed and return member data.
    """
    should_generate = request.query_params.get('generate', 'true').lower() != 'false'

    user = request.user
    up, _ = UserProfile.objects.get_or_create(user=user)
    access, limit = _pred_access(up)
    today = _pred_today()

    if access == 'none':
        return JsonResponse({'error': 'upgrade_required'}, status=403)

    if not should_generate:
        try:
            bill_pred = BillPrediction.objects.get(id=bill_id)
        except BillPrediction.DoesNotExist:
            return JsonResponse({'exists': False})

        reveal_key = f'pred_member_reveal:{user.id}:{bill_id}'

        if access == 'unlimited':
            house_members, senate_members = _build_member_predictions(bill_pred)
            return JsonResponse({
                'exists': True,
                'members_house': house_members,
                'members_senate': senate_members,
                'credits_remaining': None,
            })

        credits_remaining = _get_pred_credits_remaining(user.id, today, limit)
        if bool(cache.get(reveal_key)):
            house_members, senate_members = _build_member_predictions(bill_pred)
            return JsonResponse({
                'exists': True,
                'members_house': house_members,
                'members_senate': senate_members,
                'credits_remaining': credits_remaining,
            })
        return JsonResponse({'exists': True, 'credits_remaining': credits_remaining})

    # generate=true — spend a credit if needed
    try:
        bill_pred = BillPrediction.objects.get(id=bill_id)
    except BillPrediction.DoesNotExist:
        return JsonResponse({'error': 'no_prediction'}, status=404)

    reveal_key = f'pred_member_reveal:{user.id}:{bill_id}'
    credits_remaining = None

    if access == 'unlimited':
        pass  # premium/special: always authorized
    else:  # metered: plus / plus pro
        already_unlocked = bool(cache.get(reveal_key))
        if not already_unlocked:
            remaining = _get_pred_credits_remaining(user.id, today, limit)
            if remaining <= 0:
                return JsonResponse({'error': 'daily_limit', 'credits_remaining': 0})
            credits_remaining = _spend_pred_credit(user.id, today, limit)
            cache.set(reveal_key, True, timeout=86400)
        else:
            credits_remaining = _get_pred_credits_remaining(user.id, today, limit)

    house_members, senate_members = _build_member_predictions(bill_pred)

    return JsonResponse({
        'success': True,
        'members_house': house_members,
        'members_senate': senate_members,
        'credits_remaining': credits_remaining,
    })


@api_view(['GET'])
@authentication_classes([SessionAuthentication, JWTAuthentication])
@permission_classes([IsAuthenticated])
def prediction_usage(request):
    """Return prediction credit usage for the current user (mirrors chat_usage for predictions)."""
    up, _ = UserProfile.objects.get_or_create(user=request.user)
    access, limit = _pred_access(up)
    if access != 'metered':
        return DRFResponse({'display': 'none', 'val': None})
    today = _pred_today()
    remaining = _get_pred_credits_remaining(request.user.id, today, limit)
    return DRFResponse({'display': 'count', 'val': remaining, 'limit': limit})


def vote(request, vote_id):
    assert isinstance(request, HttpRequest)
    try:
        vote = Vote.objects.get(id = vote_id)
    except Vote.DoesNotExist:
        return render(request, 'BillQuery/search_failed.html', {
                'title': 'Vote does not exist',
                'return_url': '/bill/'
            })
    context = utils.voteHtml(vote)
    return render(
        request,
        'BillQuery/vote.html',
        context
    )

@staff_member_required
def populate_bills(request, congress_num, bill_type, limit, offset):
    assert isinstance(request, HttpRequest)
    asyncio.run(utils.addBills(congress_num, bill_type, limit, offset))
    return HttpResponseRedirect("/bill/")

@staff_member_required
def update_bill(request, congress_num, bill_type, bill_num):
    assert isinstance(request, HttpRequest)
    asyncio.run(utils.updateBill(congress_num, bill_type, bill_num))
    return HttpResponseRedirect("/bill/" + str(congress_num) + "/" + bill_type + "/" + str(bill_num))

@staff_member_required
def fix_votes(request, congress_num, year, nums):
    member_ids = request.GET['member_ids'].split(',')
    assert isinstance(request, HttpRequest)
    asyncio.run(utils.fixHouseVotes(congress_num, year, nums, member_ids))
    return HttpResponseRedirect("/bill/")

@staff_member_required
def update_bills(request, congress_num, date):
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
    return HttpResponseRedirect("/bill/")

_CHAT_SYSTEM_PROMPT = '(not included in the public snapshot)'

_DOC_TYPE_LABELS = {0: 'Bill Text', 1: 'CBO Cost Estimate', 2: 'Bill Action History'}

_SPONSOR_NEEDED_PROMPT = '(not included in the public snapshot)'


async def _query_needs_sponsor_detail(claude: anthropic.AsyncAnthropic, query: str) -> bool:
    return False


_NEEDS_RAG_PROMPT = '(not included in the public snapshot)'


async def _query_needs_rag(claude: anthropic.AsyncAnthropic, query: str) -> bool:
    return False


async def _fetch_sponsor_data(bill) -> dict:
    try:
        return await sync_to_async(lambda: {
            'name': bill.sponsor.member.full_name,
            'party': bill.sponsor.party,
            'state': bill.sponsor.state,
            'chamber': bill.sponsor.getChamber(),
        })()
    except Exception:
        return {}


async def _fetch_cosponsors_data(bill) -> list:
    try:
        return await sync_to_async(lambda: [
            {
                'name': m.member.full_name,
                'party': m.party,
                'state': m.state,
                'chamber': m.getChamber(),
            }
            for m in bill.cosponsors.select_related('member').all()
        ])()
    except Exception:
        return []


async def _fetch_related_bills_data(bill) -> list:
    try:
        return await sync_to_async(lambda: [
            {
                'identifier': f"{b.getType()} {b.getNumStr()} ({b.getCongress()}th Congress)",
                'title': b.title,
            }
            for b in bill.related_bills.all()
        ])()
    except Exception:
        return []


async def _maybe_index(bill, bill_id) -> None:
    return None


def _format_sponsor(data: dict) -> str:
    if not data:
        return "Not available"
    party_initial = data['party'][0] if data.get('party') else '?'
    return f"{data['name']} ({party_initial}-{data['state']}, {data['chamber']})"


def _format_cosponsors(data: list, needs_detail: bool) -> str:
    if not data:
        return "None"

    def fmt(m: dict) -> str:
        party_initial = m['party'][0] if m.get('party') else '?'
        return f"{m['name']} ({party_initial}-{m['state']}, {m['chamber']})"

    if needs_detail:
        return ", ".join(fmt(m) for m in data)

    preview = [fmt(m) for m in data[:3]]
    remaining = len(data) - 3
    preview_str = ", ".join(preview)
    if remaining > 0:
        return f"{preview_str}, ...and {remaining} more"
    return preview_str


def _format_related_bills(data: list) -> str:
    if not data:
        return "None"
    return "\n".join(f"- {b['identifier']}: {b['title']}" for b in data)


async def _async_web_chat(user, bill_id, message, session_id_str, daily_limit, hyper_mode: bool = False, monthly_token_limit: int = 0, monthly_search_limit: int = 0):
    return {'error': 'Chat is not included in the public snapshot.', 'messages_remaining': 0, 'session_id': None, 'assistant_message': None}


@login_required
@require_POST
def web_chat(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid request body'}, status=400)

    bill_id = data.get('bill_id')
    message = (data.get('message') or '').strip()
    session_id_str = data.get('session_id') or None
    hyper_mode = bool(data.get('hyper_mode', False))

    if not bill_id or not message:
        return JsonResponse({'error': 'Missing required fields'}, status=400)

    try:
        bill_id = int(bill_id)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid bill_id'}, status=400)

    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    daily_limit = user_profile.get_chat_limit()
    monthly_token_limit = user_profile.get_monthly_token_budget()
    monthly_search_limit = user_profile.get_monthly_web_search_limit()

    if daily_limit == 0:
        return JsonResponse({'error': 'UPGRADE_REQUIRED', 'messages_remaining': 0})

    result = asyncio.run(_async_web_chat(request.user, bill_id, message, session_id_str, daily_limit, hyper_mode, monthly_token_limit, monthly_search_limit))
    return JsonResponse(result)


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

    if summary == utils.SUMMARY_TOO_LARGE:
        return JsonResponse({'status': 'error', 'message': 'This bill is too large to generate a summary.', 'too_large': True}, status=413)

    if summary == utils.SUMMARY_OVERLOADED:
        return JsonResponse({'status': 'error', 'message': 'The AI is temporarily overloaded. Please try again in a moment.', 'retryable': True}, status=503)

    if not summary:
        return JsonResponse({'status': 'error', 'message': 'Could not generate a summary at this time.'}, status=500)

    try:
        bill_summary_obj = BillSummary.objects.get(id=bill_id)
        generated_at = bill_summary_obj.generated_at.isoformat() if bill_summary_obj.generated_at else None
    except BillSummary.DoesNotExist:
        generated_at = None

    return JsonResponse({'status': 'ok', 'summary': summary, 'generated_at': generated_at})


@api_view(['GET'])
@authentication_classes([SessionAuthentication, JWTAuthentication])
@permission_classes([IsAuthenticated])
def chat_usage(request):
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    daily_limit = user_profile.get_chat_limit()
    monthly_token_limit = user_profile.get_monthly_token_budget()

    # free users
    if daily_limit == 0:
        return DRFResponse({'display': 'none', 'val': None})

    # premium users
    if monthly_token_limit > 0:
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage = ChatMessage.objects.filter(
            session__user=request.user,
            created_at__gte=month_start,
        ).aggregate(total=Sum(F('input_tokens') + OUTPUT_TOKEN_COST_WEIGHT * F('output_tokens')))
        used = usage['total'] or 0
        pct = min(round(used / monthly_token_limit, 4), 1.0)
        return DRFResponse({'display': 'donut', 'val': pct})

    #special users
    if daily_limit >= 10000:
        return DRFResponse({'display': 'none', 'val': None})

    # fallback on pls users
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    used_today = ChatMessage.objects.filter(
        session__user=request.user,
        role=ChatMessage.Role.USER,
        created_at__gte=today_start,
    ).count()
    remaining = max(0, daily_limit - used_today)
    return DRFResponse({'display': 'count', 'val': remaining, 'limit': daily_limit})


@login_required
@require_GET
def chat_history(request):
    bill_id = request.GET.get('bill_id')
    if not bill_id:
        return JsonResponse({'error': 'Missing bill_id'}, status=400)
    try:
        bill_id = int(bill_id)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid bill_id'}, status=400)

    session = ChatSession.objects.filter(
        user=request.user, bill_id=bill_id
    ).order_by('-updated_at').first()
    if not session:
        return JsonResponse({'session_id': None, 'messages': []})

    messages = list(session.messages.order_by('created_at', 'id').values('role', 'content')[:40])
    return JsonResponse({'session_id': str(session.id), 'messages': messages})