import strawberry, aiohttp
import strawberry.types
from datetime import date, datetime
from .types import BillConnection, BillEdge, BillType, BillMemberType, VoteType, VoteConnection, VoteEdge, ActionType, CongressType, SubjectType, ChatHistoryType, ChatMessageItem
from typing import List, Optional
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramWordSimilarity
from django.db.models import F, Q, Count, Prefetch, Value, FloatField, Subquery, OuterRef
from BillQuery.models import Bill, Subject, Vote
from BillQuery.bill_reference import bill_reference_candidate_ids
from django.db.models.functions import Coalesce, Greatest
from django.core.cache import cache
from SenateQuery.models import Congress, Member, Membership
from .utils import batch_load_summaries, fetch_actions, fetch_summary
from asgiref.sync import sync_to_async
from markdownify import markdownify as md
import base64
import hashlib
import json
from rest_framework_simplejwt.tokens import AccessToken
from graphql import GraphQLError
from notifications.models import StarredBill
from app.models import UserProfile, ChatSession, ChatMessage


def encode_cursor(payload: dict) -> str:
    ## payload should be a dict, e.g. {"id": 123, "latest_action": "2025-12-19", "match_count": 2}
    return base64.b64encode(json.dumps(payload).encode()).decode()

def decode_cursor(cursor: str) -> dict:
    raw = base64.b64decode(cursor).decode()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        ## backward-compat: old cursors were just the id as a plain integer string
        try:
            return {"id": int(raw)}
        except ValueError:
            return {}

def vote_id_helper(a):
    if "recordedVotes" in a:
        in_house = 0 if (a['recordedVotes'][0]['chamber'] != 'House') else 1
        vote_id = a['recordedVotes'][0]['congress'] * 10000000 + in_house * 1000000 + int(a['recordedVotes'][0]['sessionNumber']) * 100000 + int(a['recordedVotes'][0]['rollNumber'])
        return vote_id
    return None


def selection_contains_field(info: "strawberry.types.Info", field_name: str) -> bool:
    def _check(fields):
        for field in fields:
            if field.name == field_name:
                return True
            if _check(field.selections):
                return True
        return False
    return _check(info.selected_fields)


def _get_bill_with_related(bill_id: int):
    bill = (
        Bill.objects
        .select_related("sponsor__member")
        .get(id=bill_id)
    )
    sponsor = BillMemberType(
        name=bill.sponsor.member.full_name,
        party=bill.sponsor.party,
        state=bill.sponsor.state,
    )
    cosponsors = [
        BillMemberType(name=m.member.full_name, party=m.party, state=m.state)
        for m in bill.cosponsors.select_related("member").all()
    ]
    related_bills = [int(rb.id) for rb in bill.related_bills.all()]
    return bill, sponsor, cosponsors, related_bills


@strawberry.type
class Query:
    @strawberry.field
    async def getCongressSet(self) -> List[CongressType]:
        return await sync_to_async(list)(Congress.objects.all())

    @strawberry.field
    async def getSubjectSet(self) -> List[SubjectType]:
        return await sync_to_async(list)(Subject.objects.all())

    @strawberry.field
    async def getBill(self, bill_id : int) -> Optional[BillType]:
        try:
            bill, sponsor, cosponsors, related_bills = await sync_to_async(_get_bill_with_related)(bill_id)
        except Bill.DoesNotExist:
            return None
        session = aiohttp.ClientSession()
        sum_context = await fetch_summary(session, bill, try_AI_fetch=False)
        act_context = await fetch_actions(session, bill)
        actions = [ActionType(
            actionCode=a.get("actionCode"),
            actionDate=a.get("actionDate"),
            voteId=vote_id_helper(a),
            text=a.get("text"),
            type=a.get("type"),
            ) for a in act_context.get('actions', []) if isinstance(a, dict)
        ]
        await session.close()
        return BillType(
            id = bill.id,
            policy_area = bill.policy_area,
            status = bill.status,
            title = bill.title,
            origin_date = bill.origin_date,
            latest_action = bill.latest_action,
            subjects = bill.subjects.all(),
            match_count = 0,
            summary = md(sum_context['summary']),
            is_AI_generated = sum_context['AI_generated_content?'],
            ai_summary_generated_at = sum_context.get('generated_at'),
            actions = actions,
            status_code = bill.status_code,
            veto_in_history = bill.veto_in_history,
            conf_in_history = bill.conf_in_history,
            sponsor = sponsor,
            cosponsors = cosponsors,
            related_bills = related_bills,
            )

    @strawberry.field
    async def getVote(self, vote_id : int) -> Optional[VoteType]:
        try:
            qs = (
                Vote.objects
                .filter(id=vote_id)
                .select_related("bill", "congress")
                .prefetch_related(
                    Prefetch(
                        "yeas",
                        queryset=Membership.objects.select_related("member", "congress")
                    ),
                    Prefetch(
                        "nays",
                        queryset=Membership.objects.select_related("member", "congress")
                    ),
                    Prefetch(
                        "pres",
                        queryset=Membership.objects.select_related("member", "congress")
                    ),
                    Prefetch(
                        "novt",
                        queryset=Membership.objects.select_related("member", "congress")
                    )
                )
            )
            return await qs.afirst()
        except Vote.DoesNotExist:
            return None

    @strawberry.field
    async def getRecommendedBills(
        self,
        congress_num: int = 119,
        bill_type:str = "!",
        subjectList: Optional[List[int]] = None,
        first: int = 5,
        after: Optional[str] = None,
        truncate: Optional[bool] = False,
        sort: Optional[str] = None, 
        info: "strawberry.types.Info" = None,
    ) -> BillConnection:
        return BillConnection(edges=[], page_info=strawberry.relay.PageInfo(has_next_page=False, has_previous_page=False, start_cursor=None, end_cursor=None), error='Not included in the public snapshot.')

    @strawberry.field
    async def getBillsByKeyword(
        self,
        keyword: str,
        congress_num: int = 119,
        bill_type: str = "!",
        first: int = 5,
        after: Optional[str] = None,
        truncate: Optional[bool] = False,
        sort: Optional[str] = None,
        info: "strawberry.types.Info" = None,
    ) -> BillConnection:

        return BillConnection(edges=[], page_info=strawberry.relay.PageInfo(has_next_page=False, has_previous_page=False, start_cursor=None, end_cursor=None), error='Not included in the public snapshot.')

    @strawberry.field
    async def getStarredBills(
        self,
        first: int = 5,
        after: Optional[str] = None,
        access_token: str = None,
        info: "strawberry.types.Info" = None,
    ) -> BillConnection:
        starred_ids=[]
        first = min(first, 30)

        # Early check: missing token -> return error in payload (do not raise)
        if not access_token or access_token == "":
            return BillConnection(
                edges=[],
                page_info=strawberry.relay.PageInfo(
                    has_next_page=False,
                    has_previous_page=False,
                    start_cursor=None,
                    end_cursor=None,
                ),
                error="Session expired. Please log in."
            )

        try:
            token = AccessToken(access_token)
            user_id = token.get("user_id")
            user_profile = await UserProfile.objects.aget(user__id=user_id)
            sb_qs = user_profile.get_starred_bills()
            # values_list is sync; convert to list asynchronously
            raw_ids = await sync_to_async(list)(sb_qs.values_list("bill_id", flat=True))
            # convert stored string bill ids to ints where possible
            starred_ids = []
            for _id in raw_ids:
                try:
                    starred_ids.append(int(_id))
                except Exception:
                    # skip non-integer or malformed ids
                    continue
        except GraphQLError as e:
            # return GraphQL error message in the connection payload
            return BillConnection(
                edges=[],
                page_info=strawberry.relay.PageInfo(
                    has_next_page=False,
                    has_previous_page=False,
                    start_cursor=None,
                    end_cursor=None,
                ),
                error=str(e)
            )
        except Exception as e:
            # any other failure (invalid token / user not found / db error) -> return error
            return BillConnection(
                edges=[],
                page_info=strawberry.relay.PageInfo(
                    has_next_page=False,
                    has_previous_page=False,
                    start_cursor=None,
                    end_cursor=None,
                ),
                error="Invalid access token or user not found"
            )

        qs = Bill.type_objects.filter(id__in=starred_ids)
        qs = qs.order_by("-latest_action", "-id")
        if after:
            cursor = decode_cursor(after)
            last_action_str = cursor.get("latest_action")
            last_id = cursor.get("id")
            if last_action_str and last_id is not None:
                try:
                    last_action = date.fromisoformat(last_action_str)
                    qs = qs.filter(Q(latest_action__lt=last_action) | (Q(latest_action=last_action) & Q(id__lt=last_id)))
                except Exception:
                    if last_id is not None:
                        qs = qs.filter(id__lt=last_id)
            elif last_id is not None:
                qs = qs.filter(id__lt=last_id)
        qs = qs[: first + 1]

        items = await sync_to_async(list)(qs)
        has_next = len(items) > first
        items = items[:first]
        
        ## Run summary batch request only if the GraphQL selection requests the `summary` field
        # Traverses the AST for the current field to find any selection named "summary"
        if info is not None and selection_contains_field(info, "summary"):
            summaries = await batch_load_summaries(items)
            ## Attach summaries dynamically
            for i in items:
                s = summaries.get(i.id)
                if s:
                    i.summary = md(s["summary"])
                    i.is_AI_generated = s["AI_generated_content?"]
                    i.ai_summary_generated_at = s.get("generated_at")
        else:
            for i in items:
                i.summary = None
                i.is_AI_generated = False
                i.ai_summary_generated_at = None
            
        edges = [
            BillEdge(
                cursor=encode_cursor({"id": a.id, "latest_action": a.latest_action.isoformat()}),
                node=a
            )
            for a in items
        ]

        return BillConnection(
            edges=edges,
            page_info=strawberry.relay.PageInfo(
                has_next_page=has_next,
                has_previous_page=after is not None,
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
            ),
            error="None"
        )

    @strawberry.field
    async def getRecentVotes(
        self,
        first: int = 15,
        congress_num: int = 119,
        bill_type:str = "!",
        subjectList: Optional[List[int]] = None,
        after: Optional[str] = None,
        sort: Optional[str] = None
    ) -> VoteConnection:
        first = min(first, 50)
        ## selects only from the provided congress num
        _congress = await Congress.objects.aget(congress_num__exact=congress_num)
        start_date = date(_congress.start_year, 1, 3)
        end_date = date(_congress.end_year + 1, 1, 3)
        sort = (sort or '').lower()
        qs = Vote.type_objects.get_from_type(bill_type, start_date, end_date).select_related("bill", "congress")

        ## When subjectList provided we annotate match_count based on the vote's bill subjects,
        ## require match_count > 0, and order by relevance (match_count) then recency (dateTime) then id.
        if subjectList:
            qs = qs.annotate(
                    match_count=Count(
                        "bill__subjects",
                        filter=Q(bill__subjects__in=subjectList),
                        distinct=True
                    )
                ).filter(match_count__gt=0)

            match sort:
                case "datedesc":
                    qs = qs.order_by("-dateTime", "-match_count", "-id")
                case _:
                    qs = qs.order_by("-match_count", "-dateTime", "-id")

            ## handle pagination with composite cursor (match_count, dateTime, id)
            if after:
                cursor = decode_cursor(after)
                last_match = cursor.get("match_count")
                last_dateTime_str = cursor.get("dateTime")
                last_id = cursor.get("id")
                if last_match is not None:
                    try:
                        last_match = int(last_match)
                    except Exception:
                        last_match = None
                if last_match is not None and last_dateTime_str and last_id is not None:
                    try:
                        last_dateTime = datetime.fromisoformat(last_dateTime_str)
                        match sort:
                            case "datedesc":
                                qs = qs.filter(
                                    Q(dateTime__lt=last_dateTime) |
                                    (Q(dateTime=last_dateTime) & (
                                        Q(match_count__lt=last_match) |
                                        (Q(match_count=last_match) & Q(id__lt=last_id))
                                    ))
                                )
                            case _:
                                qs = qs.filter(
                                    Q(match_count__lt=last_match) |
                                    (Q(match_count=last_match) & (
                                        Q(dateTime__lt=last_dateTime) |
                                        (Q(dateTime=last_dateTime) & Q(id__lt=last_id))
                                    ))
                                )
                    except Exception:
                        ## fallback to id-only filter (descending)
                        if last_id is not None:
                            qs = qs.filter(id__lt=last_id)
                elif last_id is not None:
                    qs = qs.filter(id__lt=last_id)

            qs = qs[: first + 1]
        else:
            ## No subject ordering required  use stable ordering by dateTime desc
            qs = qs.order_by("-dateTime", "-id")
            if after:
                cursor = decode_cursor(after)
                last_dateTime_str = cursor.get("dateTime")
                last_id = cursor.get("id")
                if last_dateTime_str and last_id is not None:
                    try:
                        last_dateTime = datetime.fromisoformat(last_dateTime_str)
                        qs = qs.filter(Q(dateTime__lt=last_dateTime) | (Q(dateTime=last_dateTime) & Q(id__lt=last_id)))
                    except Exception:
                        if last_id is not None:
                            qs = qs.filter(id__lt=last_id)
                elif last_id is not None:
                    qs = qs.filter(id__lt=last_id)
            qs = qs[: first + 1]

        items = await sync_to_async(list)(qs)
        has_next = len(items) > first
        items = items[:first]

        edges = [
            VoteEdge(
                cursor=encode_cursor({"id": a.id, "dateTime": a.dateTime.isoformat(), "match_count": getattr(a, "match_count", 0)}),
                node=a
            )
            for a in items
        ]

        return VoteConnection(
            edges=edges,
            page_info=strawberry.relay.PageInfo(
                has_next_page=has_next,
                has_previous_page=after is not None,
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
            ),
        )

    @strawberry.field
    async def getVotesByKeyword(
        self,
        keyword: str,
        first: int = 15,
        congress_num: int = 119,
        bill_type: str = "!",
        after: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> VoteConnection:

        return VoteConnection(edges=[], page_info=strawberry.relay.PageInfo(has_next_page=False, has_previous_page=False, start_cursor=None, end_cursor=None))

    @strawberry.field
    async def getChatHistory(
        self,
        bill_id: int,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ) -> ChatHistoryType:
        from rest_framework_simplejwt.tokens import RefreshToken

        user_id = None
        if access_token:
            try:
                token = AccessToken(access_token)
                user_id = token.get("user_id")
            except Exception:
                pass

        if user_id is None and refresh_token:
            try:
                rtoken = RefreshToken(refresh_token)
                user_id = rtoken.get("user_id")
            except Exception:
                pass

        if user_id is None:
            return ChatHistoryType(session_id=None, messages=[], error="Authentication required.")

        try:
            user_profile = await UserProfile.objects.select_related("user").aget(user__id=user_id)
        except UserProfile.DoesNotExist:
            return ChatHistoryType(session_id=None, messages=[], error="User not found.")

        session = await ChatSession.objects.filter(
            user=user_profile.user, bill_id=bill_id
        ).order_by('-updated_at').afirst()

        if not session:
            return ChatHistoryType(session_id=None, messages=[], error=None)

        raw = await sync_to_async(list)(
            session.messages.order_by('created_at', 'id').values('role', 'content')[:40]
        )
        messages = [ChatMessageItem(role=m['role'], content=m['content']) for m in raw]
        return ChatHistoryType(session_id=str(session.id), messages=messages, error=None)
