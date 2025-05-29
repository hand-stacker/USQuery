from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import HttpRequest, HttpResponseRedirect
from django.core.paginator import Paginator
from datetime import datetime
from app import utils, forms
from SenateQuery.models import Member, Congress, Membership
from BillQuery.models import Vote
from django.http import JsonResponse

# Create your views here.
def home(request):
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'SenateQuery/index.html',
        {   
            'title':"Senate Query",
            "mem_form" : forms.MemberForm(request.GET)
        }
    )

def search(request, congress_num, bioguide_id, in_house):
    assert isinstance(request, HttpRequest)
    API_response = utils.updateMember(congress_num, bioguide_id)
    urlPath = ""
    past_context = request.GET.dict()
    for key in past_context:
        urlPath += key + "=" + past_context[key] + "&"
        
    # find senator given member id and congress num
    try:
        congress = Congress.objects.get(congress_num = congress_num)
        member = Member.objects.get(id = bioguide_id)
        membership = Membership.objects.get(congress = congress, member = member, house = in_house)
    except:
        return HttpResponseRedirect('/member-query')
    start = membership.start_date.split('-')
    
    start_date = datetime(int(start[0]), int(start[1]), int(start[2]))
    
    if (membership.end_date == None):
        votes_in_congress = Vote.objects.filter(congress = congress, house = membership.house, dateTime__gte = start_date)
    else:
        end = membership.end_date.split('-')
        end_date = datetime(int(end[0]), int(end[1]), int(end[2]))
        votes_in_congress = Vote.objects.filter(congress = congress, house = membership.house, dateTime__gte = start_date, dateTime__lt = end_date)
    paginator = Paginator(votes_in_congress, 15)
    page_number = request.GET.get("page")
    vote_list = paginator.get_page(page_number)
    vote_table = utils.voteTable(vote_list, bioguide_id, congress_num)
    context = {
            'title': member.full_name,
            'rep_name'  : member.full_name,
            'rep_title' : 'Representative' if membership.house else "Senator",
            'rep_party' : membership.party,
            'rep_party_code' : membership.party[0],
            'rep_district' : membership.district_num,
            'rep_state' : utils.state_dict[membership.state],
            'rep_start' : membership.start_date,
            'rep_end'   : "Present" if membership.end_date == None else membership.end_date,
            'rep_img'   : member.image_link,
            'rep_twt'   : member.twitter,
            'rep_fac'   : member.facebook,
            'rep_ytb'   : member.youtube,
            'rep_phone' : member.phone,
            'rep_office': member.office,
            'congress_num'  : congress_num,
            'congress_suffix' : utils.getNumSuffix(congress_num),
            'rep_url' : member.official_link,
            "vote_table": vote_table,
            "vote_list" : vote_list,
            "urlPath" : urlPath,
        }
    
    if ('partyHistory' in API_response['member']):
        context['party_list'] = utils.partyList(API_response['member']['partyHistory'])
    if ('leadership' in API_response['member']):
        context['leadership_list'] = utils.leadershipList(API_response['member']['leadership'])
    else : context['leadership_list'] = 'None'
    if ('terms' in API_response['member']):
        context['term_list'] = utils.termList(API_response['member']['terms'], bioguide_id, congress_num)
            
    return render(
        request,
        'SenateQuery/representative.html',
        context
    )
    
def query(request):
    assert isinstance(request, HttpRequest)
    member_form = forms.MemberForm(request.GET)
    try:
        congress_num = int(member_form.data["congress"])
        in_house = member_form.data["chamber"] != 'Senate'
    except:
        print("FATAL ERR0R")
        return HttpResponseRedirect('/member-query/')        
    return search(request, congress_num, member_form.data["member"], in_house)
    

def update_members(request, congress_num, chamber, state):
    assert isinstance(request, HttpRequest)
    is_house = chamber != 'Senate'
    _congress = Congress.objects.get(congress_num__exact=congress_num)
    if (state == 'All'):
        mems =Member.objects.filter(membership__congress = _congress, membership__house = is_house)
    else :
        mems = Member.objects.filter(membership__congress = _congress, membership__state = state, membership__house = is_house)
    mems = mems.values('id', 'full_name')
    return JsonResponse({'members': list(mems)})

@staff_member_required
def populate_congress(request, congress_num):
    assert isinstance(request, HttpRequest) 
    utils.addMembersCongressAPILazy(congress_num)
    return HttpResponseRedirect('/member-query/')   

@staff_member_required
def swap_membership(request, congress_num, leaving_id, leaving_date, in_house, arriving_id = "!",arriving_date = "!", party = "!"):
    assert isinstance(request, HttpRequest)
    utils.swapMembership(congress_num, leaving_id, in_house, leaving_date, arriving_id, arriving_date, party)
    return HttpResponseRedirect('/member-query/')   

@staff_member_required
def update_arrival(request, congress_num, arriving_id, arriving_date, in_house):
    assert isinstance(request, HttpRequest)
    utils.updateArrival(congress_num, arriving_id, arriving_date, in_house)
    return HttpResponseRedirect('/member-query/')

@staff_member_required
def create_membership(request, congress_num, bioguide_id, state, in_house, party, arrival_date = None, departure_date = None, district_num = None):
    assert isinstance(request, HttpRequest)
    utils.createMembership(congress_num, bioguide_id, state, in_house, party, arrival_date, departure_date, district_num )
    return HttpResponseRedirect('/member-query/')