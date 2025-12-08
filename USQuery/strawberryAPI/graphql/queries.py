import strawberry, aiohttp
import strawberry.types
from datetime import date
from .types import BillConnection, BillEdge, BillType, VoteType, VoteConnection, VoteEdge, ActionType, CongressType, SubjectType
from typing import List, Optional
from django.db.models import Q, Count, Prefetch
from BillQuery.models import Bill, Subject, Vote
from SenateQuery.models import Congress, Member, Membership
from .utils import batch_load_summaries, fetch_actions, fetch_summary
from asgiref.sync import sync_to_async
from markdownify import markdownify as md

import base64

def encode_cursor(article_id: int) -> str:
    return base64.b64encode(str(article_id).encode()).decode()

def decode_cursor(cursor: str) -> int:
    return int(base64.b64decode(cursor).decode())

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

        ##  handles pagination
        if after:
            after_id = decode_cursor(after)
            qs = qs.filter(id__gt=after_id)

        if not subjectList:
            qs = qs[: first + 1]
        else:
            qs = (
                qs.annotate(
                    match_count=Count(
                        "subjects",
                        filter=Q(subjects__in=subjectList),
                        distinct=True
                    )
                )
                .order_by("-match_count")[: first + 1]
            )

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
                cursor=encode_cursor(a.id),
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
        after: Optional[str] = None) -> VoteConnection:
        first = min(first, 50)
        ## selects only from the provided congress num
        qs = Vote.objects.all()

        ##  handles pagination
        if after:
            after_id = decode_cursor(after)
            qs = qs.filter(id__gt=after_id)

        items = await sync_to_async(list)(qs)
        has_next = len(items) > first
        items = items[:first]

        edges = [
            VoteEdge(
                cursor=encode_cursor(a.id),
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