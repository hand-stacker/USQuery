import strawberry, aiohttp
import strawberry.types
from datetime import date
from .types import BillType, BillConnection, BillEdge
from typing import List, Optional
from django.db.models import Q, Count
from BillQuery.models import Bill, Subject
from SenateQuery.models import Congress, Member, Membership
from .utils import batch_load_summaries
from asgiref.sync import sync_to_async

import base64

def encode_cursor(article_id: int) -> str:
    return base64.b64encode(str(article_id).encode()).decode()

def decode_cursor(cursor: str) -> int:
    return int(base64.b64decode(cursor).decode())

@strawberry.type
class Query:
    @strawberry.field
    async def recommended_bills(
        self,
        congress_num: int = 119,
        bill_type:str = "!",
        subjectList: Optional[List[int]] = None,
        first: int = 5,
        after: Optional[str] = None,
    ) -> BillConnection:
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
            qs = qs.order_by("-latest_action")[: first + 1]
        else:
            qs = (
                qs.annotate(
                    match_count=Count(
                        "subjects",
                        filter=Q(subjects__in=subjectList),
                        distinct=True
                    )
                )
                .order_by("-match_count", "-latest_action")[: first + 1]
            )

        items = await sync_to_async(list)(qs)
        has_next = len(items) > first
        items = items[:first]
        
        ## Run summary batch request
        summaries = await batch_load_summaries([(
            i.getCongress(),
            i.getTypeURL(),
            i.getNum()) for i in items])

        ## Attach summaries dynamically
        for i in items:
            i.summary = summaries.get(i.id)["summary"]
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