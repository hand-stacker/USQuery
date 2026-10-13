"""Deployment-specific settings that are now driven by env vars instead of
separate master / dockerized-app copies of settings.py."""

import importlib
import os
import sys
import types

import pytest

from USQuery import settings as base_settings


def test_prompt_falls_back_to_secretss(monkeypatch):
    monkeypatch.setitem(sys.modules, 'secretss', types.SimpleNamespace(prompt='from secret file'))
    assert base_settings._secretss_prompt() == 'from secret file'


def test_prompt_fallback_absent(monkeypatch):
    monkeypatch.setitem(sys.modules, 'secretss', None)  # makes `import secretss` raise ImportError
    assert base_settings._secretss_prompt() is None


@pytest.fixture
def reload_settings(monkeypatch):
    """Re-execute USQuery/settings.py with a modified environment (no DB or
    app registry involved), then restore the original module."""
    original = sys.modules['USQuery.settings']

    def _reload(**env):
        for key, value in env.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)
        return importlib.reload(original)

    yield _reload
    monkeypatch.undo()
    importlib.reload(original)


def test_static_root_default_is_staticfiles(reload_settings):
    s = reload_settings(STATIC_ROOT_DIR=None)
    assert s.STATIC_ROOT == os.path.join(s.BASE_DIR, 'staticfiles')


def test_static_root_render(reload_settings):
    s = reload_settings(STATIC_ROOT_DIR='static')
    assert s.STATIC_ROOT == os.path.join(s.BASE_DIR, 'static')


def test_prompt_env_wins(reload_settings):
    assert reload_settings(PROMPT='env prompt').PROMPT == 'env prompt'


def test_column_list_setting_removed(reload_settings):
    assert not hasattr(reload_settings(), 'COLUMN_LIST')
