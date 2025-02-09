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
            'content':"Make a senate Query",
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
    
    in_house = (membership.chamber != 'Senate')
    votes_in_congress = Vote.objects.filter(congress = congress, house = in_house)
    
    paginator = Paginator(votes_in_congress, 15)
    page_number = request.GET.get("page")
    vote_list = paginator.get_page(page_number)
    vote_table = utils.voteTable(vote_list, member_id, congress_num)
    context = {
            'title': member.full_name,
            'rep_name'  : member.full_name,
            'rep_title' : 'Senator' if not in_house else "Representative",
            'rep_party' : membership.party,
            'rep_party_code' : membership.party[0],
            'rep_district' : membership.district_num,
            'rep_state' : membership.state,
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
        print("FATA L ER_R0R")
        return HttpResponseRedirect('/member-query/')        
    return search(request, congress_num, member_form.data["member"])
    

def update_members(request, congress_id, chamber, state):
    mems = Congress.objects.get(congress_num__exact=int(congress_id)).members.filter(membership__chamber = chamber)
    if (state != 'All') : mems = mems.filter(membership__state = state)
    mems = mems.values('id', 'full_name')
    return JsonResponse({'members': list(mems)})

@staff_member_required
def populate_congress(request, congress_id = 116):
    assert isinstance(request, HttpRequest) 
    utils.addMembersCongressAPILazy(congress_id)
    return HttpResponseRedirect("/")