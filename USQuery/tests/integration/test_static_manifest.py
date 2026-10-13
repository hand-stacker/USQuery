"""Production static files: hashed (manifest) storage.

Outside DEBUG, {% static %} must find every referenced file in the manifest
or the page 500s, and URLs must carry a content hash so Cloudflare can't keep
serving a stale copy after a deploy. This runs a real collectstatic the way
build.sh does and renders the main pages against it.
"""

import re

import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings

from tests.factories import make_congress

pytestmark = pytest.mark.django_db

MANIFEST = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
PAGES = ['/', '/about/', '/privacy-policy/', '/terms-of-service/', '/login/', '/register/',
         '/plans/', '/bill/', '/vote/', '/member/']


@pytest.fixture(scope='module')
def collected(tmp_path_factory, django_db_blocker):
    root = tmp_path_factory.mktemp('staticfiles')
    storages = {**settings.STORAGES, 'staticfiles': {'BACKEND': MANIFEST}}
    with override_settings(STATIC_ROOT=str(root), STORAGES=storages):
        call_command('collectstatic', '--noinput', '--clear', verbosity=0)
        yield root


def test_production_settings_use_manifest_storage():
    from USQuery import settings as base
    expected = 'StaticFilesStorage' if base.DEBUG else 'ManifestStaticFilesStorage'
    assert base.STORAGES['staticfiles']['BACKEND'].endswith(expected)


def test_collectstatic_writes_hashed_files(collected):
    assert (collected / 'staticfiles.json').exists()
    assert any(re.fullmatch(r'site\.[0-9a-f]{12}\.css', p.name)
               for p in (collected / 'app' / 'content').iterdir())


@pytest.mark.parametrize('path', PAGES)
def test_pages_render_with_hashed_static_urls(client, collected, path):
    make_congress(119)
    storages = {**settings.STORAGES, 'staticfiles': {'BACKEND': MANIFEST}}
    with override_settings(STATIC_ROOT=str(collected), STORAGES=storages, DEBUG=False):
        resp = client.get(path)
    assert resp.status_code == 200
    html = resp.content.decode()
    local = re.findall(r'(?:href|src)="(/static/[^"]+)"', html)
    assert local, 'page should reference local static files'
    for url in local:
        assert re.search(r'\.[0-9a-f]{12}\.\w+$', url), f'unhashed static URL {url}'
