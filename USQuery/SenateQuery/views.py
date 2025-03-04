from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import HttpRequest, HttpResponseRedirect
from django.core.paginator import Paginator
from datetime import datetime
from app import utils, forms
from SenateQuery.models import Member, Congress, Membership
from BillQuery.models import Vote, Bill
from USQuery import settings
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

def search(request, congress_num, member_id):
    assert isinstance(request, HttpRequest)
    
    API_response = utils.updateMember(congress_num, member_id)
    urlPath = ""
    past_context = request.GET.dict()
    for key in past_context:
        urlPath += key + "=" + past_context[key] + "&"
        
    # find senator given member id and congress num
    congress = Congress.objects.get(congress_num = congress_num)
    member = congress.members.get(id = member_id)
    membership = Membership.objects.get(congress = congress, member = member)
    votes_in_congress = Vote.objects.filter(congress = congress, house = membership.house, dateTime__gte = membership.start_date, dateTime__lt = membership.end_date)
    paginator = Paginator(votes_in_congress, 15)
    page_number = request.GET.get("page")
    vote_list = paginator.get_page(page_number)
    vote_table = utils.voteTable(vote_list, member_id, congress_num)
    context = {
            'title': member.full_name,
            'rep_name'  : member.full_name,
            'rep_title' : 'Representative' if membership.house else "Senator",
            'rep_party' : membership.party,
            'rep_party_code' : membership.party[0],
            'rep_district' : membership.district_num,
            'rep_state' : utils.state_dict[membership.state],
            'rep_start' : membership.start_date,
            'rep_end'   : membership.end_date,
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
        context['term_list'] = utils.termList(API_response['member']['terms'], member_id, congress_num)
            
    return render(
        request,
        'SenateQuery/representative.html',
        context
    )
    
def query(request):
    member_form = forms.MemberForm(request.GET)
    try:
        congress_num = int(member_form.data["congress"])
    except:
        print("FATAL ER_R0R")
        return HttpResponseRedirect('/member-query/')        
    return search(request, congress_num, member_form.data["member"])
    

def update_members(request, congress_id, chamber, state):
    is_house = chamber != 'Senate'
    _congress = Congress.objects.get(congress_num__exact=congress_id)
    mems = Congress.objects.get(congress_num__exact=int(congress_id)).members.filter(membership__house = is_house)
    if (state != 'All') : mems = mems.filter(membership__congress = _congress, membership__state = state)
    mems = mems.values('id', 'full_name')
    return JsonResponse({'members': list(mems)})

@staff_member_required
def populate_congress(request, congress_id = 116):
    assert isinstance(request, HttpRequest) 
    utils.addMembersCongressAPILazy(congress_id)
    return HttpResponseRedirect('/member-query/')   

@staff_member_required
def swap_membership(request, congress_id, leaving_id, leaving_date, arriving_id = "!",arriving_date = "!", party = "!"):
    assert isinstance(request, HttpRequest)
    utils.swapMembership(congress_id, leaving_id, arriving_id, leaving_date, arriving_date, party)
    return HttpResponseRedirect('/member-query/')   

@staff_member_required
def update_arrival(request, congress_id, arriving_id, arriving_date):
    assert isinstance(request, HttpRequest)
    utils.updateArrival(congress_id, arriving_id, arriving_date)
    return HttpResponseRedirect('/member-query/')

@staff_member_required
def create_membership(request, congress_id, member_id, state, in_house, party, arrival_date = None, departure_date = None, district_num = None):
    assert isinstance(request, HttpRequest)
    utils.createMembership(congress_id, member_id, state, in_house, party, arrival_date, departure_date, district_num )
    return HttpResponseRedirect('/member-query/')