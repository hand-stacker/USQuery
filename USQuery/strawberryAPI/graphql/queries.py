import strawberry
import strawberry.types
from datetime import date
from .types import BillType, BillConnection, BillEdge
from typing import List, Optional
from django.db.models import Q, F, FloatField, Sum, Count
from BillQuery.models import Bill, Subject
from SenateQuery.models import Congress, Member, Membership
from django.db.models.functions import Coalesce

import base64

def encode_cursor(article_id: int) -> str:
    return base64.b64encode(str(article_id).encode()).decode()

def decode_cursor(cursor: str) -> int:
    return int(base64.b64decode(cursor).decode())


@strawberry.type
class Query:
    @strawberry.field
    def recommended_bills(
        self,
        congress_num: int = 119,
        bill_type:str = "!",
        subjectList: Optional[List[int]] = None,
        first: int = 50,
        after: Optional[str] = None,
    ) -> BillConnection:
        _congress = Congress.objects.get(congress_num__exact=congress_num)
        start_date = date(_congress.start_year, 1, 3)
        end_date = date(_congress.end_year, 1, 3)
        ## selects only from the provided congress num
        qs = Bill.type_objects.get_from_type(bill_type, start_date, end_date)

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

        items = list(qs)
        has_next = len(items) > first
        items = items[:first]

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