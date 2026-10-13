import pytest


@pytest.fixture(scope='session', autouse=True)
def _import_urlconf():
    """Import the URLconf (and with it the strawberry schema, views and
    TensorFlow) once, up front. If the first import instead happens inside a
    freeze_time block, strawberry sees freezegun's FakeDate where it expects
    datetime.date and the schema fails to build."""
    from django.urls import get_resolver
    get_resolver().url_patterns
