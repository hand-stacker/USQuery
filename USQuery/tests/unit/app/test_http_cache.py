"""Congress.gov HTTP layer: retry policy and the single-flight cache lock."""

from types import SimpleNamespace
from unittest import mock

import aiohttp
import pytest
import requests
from django.core.cache import cache

from app import utils


# --- connect (sync) ----------------------------------------------------------

def _resp(status=200, payload=None):
    r = requests.Response()
    r.status_code = status
    r._content = b'{}' if payload is None else payload
    return r


@pytest.fixture
def no_sleep():
    with mock.patch.object(utils.time, 'sleep') as s:
        yield s


class TestConnect:
    def test_success(self, no_sleep):
        with mock.patch.object(utils.requests, 'get', return_value=_resp()) as get:
            assert utils.connect('https://x', {}).status_code == 200
        assert get.call_count == 1

    def test_retries_5xx_with_backoff(self, no_sleep):
        with mock.patch.object(utils.requests, 'get', side_effect=[_resp(503), _resp(502), _resp()]) as get:
            assert utils.connect('https://x', {}).status_code == 200
        assert get.call_count == 3
        assert [c.args[0] for c in no_sleep.call_args_list] == [0.5, 1.0]

    def test_4xx_not_retried(self, no_sleep):
        with mock.patch.object(utils.requests, 'get', return_value=_resp(404)) as get:
            assert utils.connect('https://x', {}) is None
        assert get.call_count == 1

    def test_gives_up_after_max_retries(self, no_sleep):
        with mock.patch.object(utils.requests, 'get', side_effect=requests.ConnectionError('down')) as get:
            assert utils.connect('https://x', {}, max_retries=3) is None
        assert get.call_count == 4


class TestConnectAndCacheSync:
    def test_caches_json(self, no_sleep):
        with mock.patch.object(utils.requests, 'get', return_value=_resp(payload=b'{"a": 1}')) as get:
            assert utils.connect_and_cache('https://x', {'k': 1}) == {'a': 1}
            assert utils.connect_and_cache('https://x', {'k': 1}) == {'a': 1}
        assert get.call_count == 1

    def test_failure_returns_none(self, no_sleep):
        with mock.patch.object(utils.requests, 'get', return_value=_resp(404)):
            assert utils.connect_and_cache('https://x', {}) is None


# --- connectASYNC --------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status, self.payload = status, payload or {'ok': True}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(request_info=SimpleNamespace(real_url='https://x'),
                                              history=(), status=self.status)

    async def json(self):
        return self.payload

    async def text(self):
        return 'text'


def _session(*responses):
    it = iter(responses)
    return SimpleNamespace(get=mock.Mock(side_effect=lambda *a, **k: next(it)))


@pytest.fixture
def no_async_sleep():
    with mock.patch.object(utils.asyncio, 'sleep', mock.AsyncMock()) as s:
        yield s


class TestConnectAsync:
    async def test_json(self):
        assert await utils.connectASYNC(_session(_FakeResponse()), 'https://x', '?a=1') == {'ok': True}

    async def test_text(self):
        assert await utils.connectASYNC(_session(_FakeResponse()), 'https://x', '', jsonify=False) == 'text'

    async def test_retries_5xx(self, no_async_sleep):
        session = _session(_FakeResponse(503), _FakeResponse())
        assert await utils.connectASYNC(session, 'https://x', '') == {'ok': True}
        assert session.get.call_count == 2

    async def test_4xx_returns_empty_sentinel(self, no_async_sleep):
        session = _session(_FakeResponse(404))
        assert await utils.connectASYNC(session, 'https://x', '') == ''
        assert session.get.call_count == 1


# --- connect_and_cacheASYNC (single-flight) ------------------------------------

URL, HDR = 'https://api.congress.gov/v3/bill/119/hr/1', '?api_key=k'


async def _key():
    return utils.API_CACHE_VER + await utils.make_cache_keyASYNC(URL, HDR)


class TestSingleFlight:
    async def test_cache_hit_skips_fetch(self):
        cache.set(await _key(), {'cached': 1})
        with mock.patch.object(utils, 'connectASYNC', mock.AsyncMock()) as fetch:
            assert await utils.connect_and_cacheASYNC(None, URL, HDR) == {'cached': 1}
        fetch.assert_not_awaited()

    async def test_leader_fetches_caches_and_releases(self):
        key = await _key()
        with mock.patch.object(utils, 'connectASYNC', mock.AsyncMock(return_value={'fresh': 1})):
            assert await utils.connect_and_cacheASYNC(None, URL, HDR) == {'fresh': 1}
        assert key.startswith('v2:')
        assert cache.get(key) == {'fresh': 1}
        assert cache.get('lock:' + key) is None

    async def test_failure_not_cached(self):
        key = await _key()
        with mock.patch.object(utils, 'connectASYNC', mock.AsyncMock(return_value='')):
            assert await utils.connect_and_cacheASYNC(None, URL, HDR) == ''
        assert cache.get(key) is None
        assert cache.get('lock:' + key) is None

    async def test_waiter_picks_up_leaders_result(self, no_async_sleep):
        key = await _key()
        cache.add('lock:' + key, 1)
        no_async_sleep.side_effect = lambda _: cache.set(key, {'from_leader': 1})
        with mock.patch.object(utils, 'connectASYNC', mock.AsyncMock()) as fetch:
            assert await utils.connect_and_cacheASYNC(None, URL, HDR) == {'from_leader': 1}
        fetch.assert_not_awaited()
        assert no_async_sleep.await_count == 1
        assert cache.get('lock:' + key) == 1  # waiter never touches the lock

    async def test_waiter_times_out_and_fetches_without_releasing(self, no_async_sleep):
        key = await _key()
        cache.add('lock:' + key, 1)
        with mock.patch.object(utils, 'connectASYNC', mock.AsyncMock(return_value={'mine': 1})) as fetch:
            assert await utils.connect_and_cacheASYNC(None, URL, HDR) == {'mine': 1}
        assert no_async_sleep.await_count == 28
        fetch.assert_awaited_once()
        assert cache.get('lock:' + key) == 1

    async def test_lock_backend_error_falls_back_to_fetch(self):
        with mock.patch.object(utils.cache, 'aadd', mock.AsyncMock(side_effect=ConnectionError('redis'))), \
             mock.patch.object(utils, 'connectASYNC', mock.AsyncMock(return_value={'ok': 1})):
            assert await utils.connect_and_cacheASYNC(None, URL, HDR) == {'ok': 1}
