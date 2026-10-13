"""Fire-and-forget logging of AI API usage that isn't captured on ChatMessage.

These helpers must never raise: cost tracking failing should never break the
feature that triggered it.
"""
from app.models import ApiUsageEvent


def log_usage(service: int, purpose: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
    try:
        ApiUsageEvent.objects.create(
            service=service,
            purpose=purpose,
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
        )
    except Exception as e:
        print(f"usage_tracking: failed to log {purpose}: {e}")


async def alog_usage(service: int, purpose: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
    try:
        await ApiUsageEvent.objects.acreate(
            service=service,
            purpose=purpose,
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
        )
    except Exception as e:
        print(f"usage_tracking: failed to log {purpose}: {e}")
