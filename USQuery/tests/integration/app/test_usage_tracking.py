"""log_usage / alog_usage write an ApiUsageEvent and must never raise."""

from unittest import mock

import pytest

from app.models import ApiUsageEvent
from app.usage_tracking import alog_usage, log_usage

CLAUDE = ApiUsageEvent.Service.CLAUDE


@pytest.mark.django_db
def test_log_usage_writes_row():
    log_usage(CLAUDE, 'summary', 100, 20)
    event = ApiUsageEvent.objects.get()
    assert (event.purpose, event.input_tokens, event.output_tokens) == ('summary', 100, 20)


@pytest.mark.django_db
def test_none_tokens_stored_as_zero():
    log_usage(CLAUDE, 'summary', None, None)
    assert ApiUsageEvent.objects.get().input_tokens == 0


@pytest.mark.django_db
def test_log_usage_swallows_errors():
    with mock.patch.object(ApiUsageEvent.objects, 'create', side_effect=RuntimeError('db down')):
        log_usage(CLAUDE, 'summary', 1, 1)


@pytest.mark.django_db(transaction=True)
async def test_alog_usage_writes_row():
    await alog_usage(ApiUsageEvent.Service.VOYAGE, 'indexing', 500)
    assert await ApiUsageEvent.objects.filter(purpose='indexing').acount() == 1


@pytest.mark.django_db(transaction=True)
async def test_alog_usage_swallows_errors():
    with mock.patch.object(ApiUsageEvent.objects, 'acreate', side_effect=RuntimeError('db down')):
        await alog_usage(CLAUDE, 'summary', 1, 1)
