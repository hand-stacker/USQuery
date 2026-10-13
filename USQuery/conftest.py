"""Root pytest configuration.

Safety first: the session aborts before any query if the configured database
isn't the disposable test container, and every test runs with outbound
network access blocked unless it is marked `external`.
"""

import socket
import sys
from pathlib import Path

import pytest

from tests.safety import UnsafeDatabaseError, check_database_is_disposable

_ROOT = Path(__file__).resolve().parent
_UNIT_DIR = _ROOT / 'tests' / 'unit'
_INTEGRATION_DIR = _ROOT / 'tests' / 'integration'


# --- database guard ---------------------------------------------------------

def _guard_database():
    from django.conf import settings
    try:
        check_database_is_disposable(settings.DATABASES['default'])
    except UnsafeDatabaseError as exc:
        pytest.exit(str(exc), returncode=3)


def pytest_configure(config):
    _guard_database()


@pytest.fixture(scope='session')
def django_db_setup(request, django_db_setup):
    # Re-checked right before pytest-django creates/migrates the test DB, in
    # case anything mutated settings after configure.
    _guard_database()
    yield


# --- markers by directory ---------------------------------------------------

def pytest_collection_modifyitems(config, items):
    for item in items:
        path = Path(str(item.fspath)).resolve()
        if _UNIT_DIR in path.parents:
            item.add_marker(pytest.mark.unit)
        elif _INTEGRATION_DIR in path.parents:
            item.add_marker(pytest.mark.integration)


# --- network blocker --------------------------------------------------------

class UnmockedNetworkCall(AssertionError):
    pass


_LOOPBACK = {'127.0.0.1', '::1', 'localhost'}


def _is_loopback(address):
    host = address[0] if isinstance(address, tuple) else address
    return isinstance(host, (str, bytes)) and (
        host.decode() if isinstance(host, bytes) else host) in _LOOPBACK


def _raise_unmocked(target):
    raise UnmockedNetworkCall(
        f'Unmocked network call to {target!r}. Patch the client (requests, '
        'aiohttp, stripe, anthropic, voyageai, ...) or mark the test '
        '@pytest.mark.external.'
    )


@pytest.fixture(autouse=True)
def no_network(request, monkeypatch):
    """Block non-loopback sockets. Loopback stays open because asyncio's
    Windows event loop uses a socketpair internally. psycopg2 connects through
    libpq's own C sockets, so the test database is unaffected either way."""
    if request.node.get_closest_marker('external'):
        return

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def connect(self, address):
        if not _is_loopback(address):
            _raise_unmocked(address)
        return real_connect(self, address)

    def connect_ex(self, address):
        if not _is_loopback(address):
            _raise_unmocked(address)
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if not _is_loopback((host,)):
            _raise_unmocked(host)
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, 'connect', connect)
    monkeypatch.setattr(socket.socket, 'connect_ex', connect_ex)
    monkeypatch.setattr(socket, 'getaddrinfo', getaddrinfo)


# --- per-test state reset ---------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_module_state():
    """Clear the locmem cache and app.utils' per-run accumulators so tests
    can't leak state into each other."""
    yield
    from django.core.cache import cache
    cache.clear()
    utils = sys.modules.get('app.utils')
    if utils is not None:
        utils._senate_bill_ids_this_run.clear()
        utils._house_bill_ids_this_run.clear()


# --- shared fixtures --------------------------------------------------------

@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def congress_119(db):
    from tests.factories import make_congress
    return make_congress(119)


@pytest.fixture
def free_user(db):
    from tests.factories import make_user
    return make_user(tier=0)


@pytest.fixture
def plus_user(db):
    from tests.factories import make_user
    return make_user(tier=1)


@pytest.fixture
def plus_pro_user(db):
    from tests.factories import make_user
    return make_user(tier=4)


@pytest.fixture
def premium_user(db):
    from tests.factories import make_user
    return make_user(tier=2)
