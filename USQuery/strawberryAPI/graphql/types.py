import strawberry_django
import strawberry
from BillQuery.models import Bill, Subject
from SenateQuery.models import Membership, Member, Congress
from strawberry import auto


## Bill related types
@strawberry.type
class BillEdge:
    cursor: str
    node: "BillType"

@strawberry.type
class BillConnection:
    edges: list["BillEdge"]
    page_info: strawberry.relay.PageInfo


@strawberry_django.type(Bill)
class BillType:
    id: auto
    sponsor: "MembershipType"
    cosponsors : list["MembershipType"]
    policy_area : auto
    status : auto
    title : auto
    origin_date : auto
    latest_action : auto
    subjects : list["SubjectType"]
    match_count: int | None = None
    summary : str | None = None

@strawberry_django.type(Subject)
class SubjectType:
    id: auto
    name : str
    subtype : int



## Member related types
@strawberry_django.type(Membership)
class MembershipType:
    id: auto
    congress : "CongressType"
    member : "MemberType"
    district_num : int
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
    congress_num: auto
    