import strawberry, aiohttp
import strawberry.types
from datetime import date, datetime
from .types import BillConnection, BillEdge, BillType, VoteType, VoteConnection, VoteEdge, ActionType, CongressType, SubjectType
from typing import List, Optional
from django.db.models import Q, Count, Prefetch
from BillQuery.models import Bill, Subject, Vote
from SenateQuery.models import Congress, Member, Membership
from .utils import batch_load_summaries, fetch_actions, fetch_summary
from asgiref.sync import sync_to_async
from markdownify import markdownify as md
import base64
import json

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
            bill = await Bill.objects.aget(id = bill_id)
        except Bill.DoesNotExist:
            return None 
        session = aiohttp.ClientSession()
        sum_context = await fetch_summary(session, bill)
        act_context = await fetch_actions(session,bill)
        actions = [ActionType(
            actionCode=a.get("actionCode"),
            actionDate=a.get("actionDate"),
            voteId=vote_id_helper(a),
            text=a.get("text"),
            type=a.get("type"),
            ) for a in act_context['actions']
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
            summary =md(sum_context['summary']) ,
            is_AI_generated = sum_context['AI_generated_content?'],
            actions = actions
            )

    @strawberry.field
    async def getVote(self, vote_id : int) -> Optional[VoteType]:
        try:
            qs = (
                Vote.objects
                .filter(id=vote_id)
                .prefetch_related(
                    Prefetch(
                        "yeas",
                        queryset=Membership.objects.select_related("member")
                    ),
                    Prefetch(
                        "nays",
                        queryset=Membership.objects.select_related("member")
                    ),
                    Prefetch(
                        "pres",
                        queryset=Membership.objects.select_related("member")
                    ),
                    Prefetch(
                        "novt",
                        queryset=Membership.objects.select_related("member")
                    )
                )
            )
            return await qs.afirst()
        except Vote.DoesNotExist:
            return None

    @strawberry.field
    async def recommended_bills(
        self,
        congress_num: int = 119,
        bill_type:str = "!",
        subjectList: Optional[List[int]] = None,
        first: int = 5,
        after: Optional[str] = None,
    ) -> BillConnection:
        first = min(first, 15)
        _congress = await Congress.objects.aget(congress_num__exact=congress_num)
        start_date = date(_congress.start_year, 1, 3)
        end_date = date(_congress.end_year, 1, 3)

        ## selects only from the provided congress num
        qs = Bill.type_objects.get_from_type(bill_type, start_date, end_date)

        ## When subjectList provided we annotate match_count, require match_count > 0,
        ## and order by relevance (match_count) then recency (latest_action) then id for stability.
        if subjectList:
            qs = qs.annotate(
                    match_count=Count(
                        "subjects",
                        filter=Q(subjects__in=subjectList),
                        distinct=True
                    )
                ).filter(match_count__gt=0)

            qs = qs.order_by("-match_count", "-latest_action", "-id")

            ## handle pagination with composite cursor (match_count, latest_action, id)
            if after:
                cursor = decode_cursor(after)
                last_match = cursor.get("match_count")
                last_action_str = cursor.get("latest_action")
                last_id = cursor.get("id")
                if last_match is not None:
                    try:
                        last_match = int(last_match)
                    except Exception:
                        last_match = None
                if last_match is not None and last_action_str and last_id is not None:
                    try:
                        last_action = date.fromisoformat(last_action_str)
                        ## ordering is descending: choose rows that come after the cursor:
                        ## 1) match_count < last_match
                        ## 2) OR match_count == last_match AND latest_action < last_action
                        ## 3) OR match_count == last_match AND latest_action == last_action AND id < last_id
                        qs = qs.filter(
                            Q(match_count__lt=last_match) |
                            (Q(match_count=last_match) & (
                                Q(latest_action__lt=last_action) |
                                (Q(latest_action=last_action) & Q(id__lt=last_id))
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
            ## No subject ordering required use stable ordering by latest_action desc
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
        
        ## Run summary batch request
        summaries = await batch_load_summaries([i for i in items])

        ## Attach summaries dynamically
        for i in items:
            i.summary = md(summaries.get(i.id)["summary"])
            i.is_AI_generated = summaries.get(i.id)["AI_generated_content?"]
            
        edges = [
            BillEdge(
                cursor=encode_cursor({"id": a.id, "latest_action": a.latest_action.isoformat(), "match_count": getattr(a, "match_count", 0)}),
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
        )

    @strawberry.field
    async def get_recent_votes(
        self,
        first: int = 15,
        congress_num: int = 119,
        bill_type:str = "!",
        subjectList: Optional[List[int]] = None,
        after: Optional[str] = None) -> VoteConnection:
        first = min(first, 50)
        ## selects only from the provided congress num
        _congress = await Congress.objects.aget(congress_num__exact=congress_num)
        start_date = date(_congress.start_year, 1, 3)
        end_date = date(_congress.end_year, 1, 3)
        qs = Vote.type_objects.get_from_type(bill_type, start_date, end_date)

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
                        ## ordering is descending: choose rows that come after the cursor:
                        ## 1) match_count < last_match
                        ## 2) OR match_count == last_match AND dateTime < last_dateTime
                        ## 3) OR match_count == last_match AND dateTime == last_dateTime AND id < last_id
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