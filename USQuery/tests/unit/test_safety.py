"""The production-database guard is the most important code in the suite."""

import socket

import pytest
from django.conf import settings

from tests.safety import UnsafeDatabaseError, check_database_is_disposable

PG = 'django.db.backends.postgresql'


def _db(host='localhost', port=5433, name='usquery_test', engine=PG):
    return {'ENGINE': engine, 'HOST': host, 'PORT': port, 'NAME': name}


def test_configured_test_database_is_accepted():
    check_database_is_disposable(settings.DATABASES['default'], ci=False)


@pytest.mark.parametrize('db', [
    _db(),
    _db(host='127.0.0.1'),
    _db(host='test-db', port=5432),
    _db(name='test_usquery_test'),
])
def test_disposable_databases_accepted(db):
    check_database_is_disposable(db, ci=False)


@pytest.mark.parametrize('db', [
    _db(host='dpg-abc123-a.oregon-postgres.render.com', port=5432, name='usquery'),
    _db(host='dpg-abc123-a', port=5432, name='usquery'),
    _db(port=5432),                     # local PG17 install, not the container
    _db(name='usquery'),                # right container, wrong database
    _db(host=''),                       # unix socket / unset
    _db(engine='django.db.backends.sqlite3'),
])
def test_non_test_databases_rejected(db):
    with pytest.raises(UnsafeDatabaseError):
        check_database_is_disposable(db, ci=False)


def test_ci_requires_localhost():
    with pytest.raises(UnsafeDatabaseError):
        check_database_is_disposable(_db(host='test-db', port=5432), ci=True)
    check_database_is_disposable(_db(), ci=True)


def test_settings_never_point_at_production_services():
    assert 'render.com' not in str(settings.DATABASES['default'].get('HOST'))
    assert settings.CACHES['default']['BACKEND'].endswith('LocMemCache')
    assert settings.EMAIL_BACKEND.endswith('locmem.EmailBackend')


def test_network_is_blocked():
    with pytest.raises(AssertionError, match='Unmocked network call'):
        socket.create_connection(('api.congress.gov', 443), timeout=1)


def test_database_access_is_blocked_in_unit_tests():
    from django.contrib.auth.models import User
    with pytest.raises(RuntimeError, match='Database access not allowed'):
        User.objects.count()
