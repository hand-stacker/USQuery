"""Guards that keep the test suite away from production services.

Kept separate from conftest.py so the guard itself is unit-tested
(tests/unit/test_safety.py).
"""

import os

ALLOWED_DB_HOSTS = {'localhost', '127.0.0.1', 'test-db'}
ALLOWED_DB_PORTS = {'5433', '5432'}
ALLOWED_DB_NAMES = {'usquery_test'}


class UnsafeDatabaseError(Exception):
    pass


def check_database_is_disposable(db, ci=None):
    """Raise UnsafeDatabaseError unless `db` (a DATABASES entry) is the
    disposable test container.

    Port 5432 is only accepted for the docker-compose service name `test-db`
    (container-to-container); from the host the container is on 5433, which
    keeps it distinct from the local PG17 install on 5432.
    """
    if ci is None:
        ci = os.environ.get('CI', '').lower() == 'true'

    host = str(db.get('HOST') or '')
    port = str(db.get('PORT') or '')
    name = str(db.get('NAME') or '')
    engine = str(db.get('ENGINE') or '')

    problems = []
    if 'postgresql' not in engine:
        problems.append(f'engine {engine!r} is not PostgreSQL')
    if host not in ALLOWED_DB_HOSTS:
        problems.append(f'host {host!r} is not one of {sorted(ALLOWED_DB_HOSTS)}')
    if ci and host != 'localhost':
        problems.append(f'host {host!r} is not localhost (required in CI)')
    if port not in ALLOWED_DB_PORTS or (port == '5432' and host != 'test-db'):
        problems.append(f'port {port!r} is not the test container port (5433)')
    if name not in ALLOWED_DB_NAMES and not name.startswith('test_'):
        problems.append(f'database name {name!r} is not a test database')

    if problems:
        raise UnsafeDatabaseError(
            'Refusing to run tests against a non-test database: '
            + '; '.join(problems)
            + '. Tests must use the disposable test-db container '
            '(see USQuery/USQuery/test_settings.py).'
        )
