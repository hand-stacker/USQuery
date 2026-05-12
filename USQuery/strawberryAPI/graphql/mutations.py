import strawberry
import uuid as uuid_lib
from typing import Optional
from django.utils import timezone
from django.conf import settings
from asgiref.sync import sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
import anthropic

from BillQuery.models import Bill, BillSummary
from app.models import UserProfile, ChatSession, ChatMessage, BillChunk
from app.rag import index_bill, retrieve_relevant_chunks
from .types import ChatMessageResponseType


_SYSTEM_PROMPT = """You are a legislative assistant helping citizens understand U.S. legislation. You are answering questions about the following bill:

Title: {title}
Policy Area: {policy_area}
Subjects: {subjects}

Relevant bill text (retrieved based on the user's question):
{context}

Guidelines:
- Base your answers only on the bill text provided above.
- When making claims, cite the specific section or passage from the retrieved text.
- If the retrieved text does not cover the user's question, say so honestly rather than guessing.
- Ask the user clarifying questions when their personal context would improve your answer (e.g., profession, state, family situation).
- Keep responses accessible to the general public — explain legal or legislative terms when you use them.
- Do not speculate about or fabricate legislative details not present in the provided text."""


def _auth_error(msg: str) -> ChatMessageResponseType:
    return ChatMessageResponseType(session_id=None, assistant_message=None, error=msg, messages_remaining=0)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def send_chat_message(
        self,
        access_token: str,
        bill_id: int,
        message: str,
        session_id: Optional[str] = None,
    ) -> ChatMessageResponseType:

        # --- Auth ---
        if not access_token:
            return _auth_error("Authentication required.")

        try:
            token = AccessToken(access_token)
            user_id = token.get("user_id")
            user_profile = await UserProfile.objects.select_related("user").aget(user__id=user_id)
        except Exception:
            return _auth_error("Invalid or expired token.")

        # --- Tier gate ---
        daily_limit = user_profile.get_chat_limit()
        if daily_limit == 0:
            return _auth_error("UPGRADE_REQUIRED")

        # --- Rate limit check ---
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        daily_count = await ChatMessage.objects.filter(
            session__user=user_profile.user,
            role=ChatMessage.Role.USER,
            created_at__gte=today_start,
        ).acount()

        is_unlimited = daily_limit >= 10000
        if not is_unlimited and daily_count >= daily_limit:
            return ChatMessageResponseType(
                session_id=None, assistant_message=None,
                error="RATE_LIMITED", messages_remaining=0,
            )

        # --- Fetch bill context ---
        try:
            bill = await Bill.objects.aget(id=bill_id)
        except Bill.DoesNotExist:
            return ChatMessageResponseType(
                session_id=None, assistant_message=None,
                error="Bill not found.", messages_remaining=_remaining(daily_limit, daily_count),
            )

        subject_names = await sync_to_async(list)(bill.subjects.values_list("name", flat=True))
        subjects = ", ".join(subject_names) or "None listed"

        # Index the bill on first chat if not already indexed
        is_indexed = await BillChunk.objects.filter(bill_id=bill_id).aexists()
        if not is_indexed:
            await index_bill(bill)

        # Retrieve chunks relevant to the user's question
        relevant_chunks = await retrieve_relevant_chunks(bill_id, message)

        if relevant_chunks:
            context_text = "\n\n---\n\n".join(
                f"[Excerpt {i + 1}]\n{chunk}" for i, chunk in enumerate(relevant_chunks)
            )
        else:
            # Fall back to stored summary if RAG has no data (bill text unavailable)
            try:
                bill_summary_obj = await BillSummary.objects.aget(id=bill_id)
                context_text = bill_summary_obj.summary
            except BillSummary.DoesNotExist:
                context_text = "No bill text is available for this bill."

        system_prompt = _SYSTEM_PROMPT.format(
            title=bill.title,
            policy_area=bill.policy_area or "General",
            subjects=subjects,
            context=context_text,
        )

        # --- Session ---
        session = None
        if session_id:
            try:
                session = await ChatSession.objects.aget(
                    id=uuid_lib.UUID(session_id), user=user_profile.user, bill_id=bill_id
                )
            except (ChatSession.DoesNotExist, ValueError):
                session = None

        if session is None:
            session = await ChatSession.objects.acreate(user=user_profile.user, bill_id=bill_id)

        # --- Build message history (last 20 exchanges) ---
        history_qs = session.messages.order_by("-created_at").values("role", "content")
        raw_history = await sync_to_async(list)(history_qs[:40])
        raw_history.reverse()
        history = [{"role": m["role"], "content": m["content"]} for m in raw_history]
        history.append({"role": "user", "content": message})

        # --- Call Anthropic ---
        try:
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            response = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system_prompt,
                messages=history,
            )
            assistant_text = response.content[0].text
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
        except Exception as e:
            return ChatMessageResponseType(
                session_id=str(session.id), assistant_message=None,
                error="AI service unavailable. Please try again.",
                messages_remaining=_remaining(daily_limit, daily_count),
            )

        # --- Persist messages ---
        await ChatMessage.objects.acreate(
            session=session, role=ChatMessage.Role.USER,
            content=message, input_tokens=input_tokens, output_tokens=0,
        )
        await ChatMessage.objects.acreate(
            session=session, role=ChatMessage.Role.ASSISTANT,
            content=assistant_text, input_tokens=0, output_tokens=output_tokens,
        )

        return ChatMessageResponseType(
            session_id=str(session.id),
            assistant_message=assistant_text,
            error=None,
            messages_remaining=_remaining(daily_limit, daily_count + 1),
        )


def _remaining(daily_limit: int, used: int) -> int:
    if daily_limit >= 10000:
        return -1  # -1 means unlimited
    return max(0, daily_limit - used)
