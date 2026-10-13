import asyncio
import strawberry
import uuid as uuid_lib
from typing import Optional, List
from django.utils import timezone
from django.db.models import Sum, F
from django.conf import settings
from asgiref.sync import sync_to_async
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from django.core.cache import cache
import anthropic

from BillQuery.models import Bill, BillSummary
from app.models import (
    UserProfile, ChatSession, ChatMessage, ApiUsageEvent, OUTPUT_TOKEN_COST_WEIGHT,
)
from app.rag import index_bill, retrieve_relevant_chunks
from app.usage_tracking import alog_usage
from .types import ChatMessageResponseType
from .utils import SUMMARY_TEXT_KEY


_SYSTEM_PROMPT = '(not included in the public snapshot)'

_DOC_TYPE_LABELS = {0: 'Bill Text', 1: 'CBO Cost Estimate', 2: 'Bill Action History'}

_NEEDS_RAG_PROMPT = '(not included in the public snapshot)'


async def _query_needs_rag(client: anthropic.AsyncAnthropic, query: str) -> bool:
    return False


async def _maybe_index_bill(bill, bill_id) -> None:
    return None


def _auth_error(msg: str) -> ChatMessageResponseType:
    return ChatMessageResponseType(
        session_id=None, assistant_message=None, error=msg,
        messages_remaining=0, sources=None, monthly_cost_pct=None, new_access_token=None,
    )


def _access_from_refresh(raw_refresh: str):
    """(user_id, new access token) from a refresh token.

    Sync on purpose: constructing a RefreshToken checks the blacklist table, so
    it must run via sync_to_async rather than inside the event loop. The refresh
    token is not rotated or blacklisted here -- this response has no field to
    hand back a replacement, so blacklisting would strand the client without a
    usable refresh token.
    """
    rtoken = RefreshToken(raw_refresh)
    return rtoken.get("user_id"), str(rtoken.access_token)


def _remaining(daily_limit: int, used: int) -> int:
    if daily_limit >= 10000:
        return -1
    return max(0, daily_limit - used)


async def _compute_monthly_token_pct(user, monthly_token_limit: int) -> Optional[float]:
    if monthly_token_limit == 0:
        return None
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage = await ChatMessage.objects.filter(
        session__user=user,
        created_at__gte=month_start,
    ).aaggregate(total=Sum(F('input_tokens') + OUTPUT_TOKEN_COST_WEIGHT * F('output_tokens')))
    used = usage['total'] or 0
    return min(round(used / monthly_token_limit, 4), 1.0)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def send_chat_message(
        self,
        bill_id: int,
        message: str,
        session_id: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        hyper_mode: bool = False,
    ) -> ChatMessageResponseType:

        # --- Auth: try access token, fall back to refresh token ---
        return _auth_error('Chat is not included in the public snapshot.')
