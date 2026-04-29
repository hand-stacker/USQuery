import strawberry_django
import strawberry
from typing import Optional, List
from BillQuery.models import Bill, Subject, Vote
from SenateQuery.models import Membership, Member, Congress
from strawberry import auto


## Vote related types
@strawberry.type
class VoteEdge:
    cursor : str
    node : "VoteType"

@strawberry.type
class VoteConnection:
    edges : list["VoteEdge"]
    page_info : strawberry.relay.PageInfo

@strawberry_django.type(Vote)
class VoteType:
    id : auto
    title : auto
    question : auto
    dateTime : auto
    bill : "BillType"
    result : str
    yeas : list["MembershipType"]
    nays : list["MembershipType"]
    pres : list["MembershipType"]
    novt : list["MembershipType"]

## Bill related types
@strawberry.type
class BillMemberType:
    name: str
    party: str
    state: str

@strawberry.type
class BillEdge:
    cursor : str
    node : "BillType"

@strawberry.type
class BillConnection:
    edges : list["BillEdge"]
    page_info : strawberry.relay.PageInfo
    error : str


@strawberry_django.type(Bill)
class BillType:
    id : auto
    policy_area : auto
    status : auto
    title : auto
    origin_date : auto
    latest_action : auto
    subjects : list["SubjectType"]
    match_count : int | None = None
    summary : str | None = None
    is_AI_generated : bool | None = False
    actions: List["ActionType"]
    current_stage: int | None = None
    sponsor: Optional["BillMemberType"] = None
    cosponsors: List["BillMemberType"] = strawberry.field(default_factory=list)
    related_bills: List[int] = strawberry.field(default_factory=list)

@strawberry.type
class ActionType:
    actionCode: str | None = None
    actionDate: str | None = None
    voteId : int | None = None
    text: Optional[str]
    type: Optional[str]

@strawberry_django.type(Subject)
class SubjectType:
    id : auto
    name : str
    subtype : int



## Member related types
@strawberry_django.type(Membership)
class MembershipType:
    id: auto
    congress : "CongressType"
    member : "MemberType"
    district_num : int | None = None
    house : bool
    state : str
    geoid : str
    party : str
    start_date : auto
    end_date : auto

@strawberry_django.type(Member)
class MemberType:
    id: auto
    full_name : str
    first_name : str
    last_name : str
    image_link : str
    office : str
    phone : str

@strawberry_django.type(Congress)
class CongressType:
    congress_num : auto
    start_year : auto
    end_year : auto


@strawberry.type
class ChatMessageResponseType:
    session_id: Optional[str]
    assistant_message: Optional[str]
    error: Optional[str]
    messages_remaining: int
