"""Regression tests for PAMS MySQL SSL configuration.

These tests verify that the SSL helpers produce the correct types for
each MySQL driver:

- **aiomysql** (async) requires ``ssl.SSLContext`` — a plain dict causes
  ``AttributeError`` in uvloop's SSL protocol layer.
- **pymysql** (sync) accepts either an ``ssl.SSLContext`` or a dict;
  the dict form ``{"ssl": {"ca": "<path>"}}`` is conventional.

RCA reference: ISSUE-001 — vehicle-checklists 503 caused by passing a
dict to aiomysql's ``connect_args["ssl"]``.
"""

import importlib
import importlib.util
import os
import ssl
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import certifi
import pytest

_REAL_CA = certifi.where()

# Locate the module file directly
_MOD_PATH = Path(__file__).resolve().parents[2] / "src" / "infrastructure" / "pams_database.py"


def _load_pams_isolated(pams_ssl_ca: str = _REAL_CA):
    """Load pams_database.py as a standalone module, bypassing the heavy
    ``src.infrastructure.__init__`` package that needs a live DB URL and
    Python 3.10+ syntax in unrelated modules.
    """
    mock_settings = MagicMock()
    mock_settings.pams_ssl_ca = pams_ssl_ca
    mock_settings.pams_database_url = "mysql+aiomysql://u:p@host/db"

    fake_config = types.ModuleType("src.core.config")
    fake_config.settings = mock_settings

    saved = {}
    for key in ("src.core.config", "src.core"):
        saved[key] = sys.modules.get(key)
        sys.modules[key] = fake_config if key == "src.core.config" else types.ModuleType(key)

    try:
        spec = importlib.util.spec_from_file_location(
            "pams_database_test", str(_MOD_PATH)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, mock_settings
    finally:
        for key, val in saved.items():
            if val is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = val


class TestBuildAsyncSslContext:
    """_build_async_ssl_context must return an ssl.SSLContext, never a dict."""

    def test_returns_ssl_context(self):
        mod, _ = _load_pams_isolated()
        ctx = mod._build_async_ssl_context()
        assert isinstance(ctx, ssl.SSLContext), (
            f"aiomysql requires ssl.SSLContext, got {type(ctx).__name__}"
        )

    def test_returns_none_when_no_ca(self):
        mod, _ = _load_pams_isolated(pams_ssl_ca="")
        assert mod._build_async_ssl_context() is None

    def test_verify_mode_is_cert_required(self):
        mod, _ = _load_pams_isolated()
        ctx = mod._build_async_ssl_context()
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_x509_strict_flag_cleared(self):
        mod, _ = _load_pams_isolated()
        ctx = mod._build_async_ssl_context()
        assert not (ctx.verify_flags & ssl.VERIFY_X509_STRICT)


class TestBuildSyncSslDict:
    """_build_sync_ssl_dict must return a dict with 'ssl' key."""

    def test_returns_dict_not_ssl_context(self):
        mod, _ = _load_pams_isolated()
        result = mod._build_sync_ssl_dict()
        assert isinstance(result, dict)
        assert "ssl" in result
        assert isinstance(result["ssl"], dict)
        assert "ca" in result["ssl"]

    def test_returns_empty_dict_when_no_ca(self):
        mod, _ = _load_pams_isolated(pams_ssl_ca="")
        assert mod._build_sync_ssl_dict() == {}


class TestResolveCAFile:
    """_resolve_ca_file prefers system CA bundle over single-cert file."""

    def test_falls_back_to_pams_ssl_ca_when_no_system_ca(self):
        mod, mock_settings = _load_pams_isolated()
        orig_exists = os.path.exists
        mod.os.path.exists = lambda p: False
        try:
            result = mod._resolve_ca_file()
            assert result == mock_settings.pams_ssl_ca
        finally:
            mod.os.path.exists = orig_exists

    def test_returns_system_ca_when_available(self):
        mod, _ = _load_pams_isolated()
        mod.os.path.exists = lambda p: True
        try:
            assert mod._resolve_ca_file() == mod._SYSTEM_CA
        finally:
            mod.os.path.exists = os.path.exists


class TestDriverTypeInvariant:
    """The two helpers must NEVER return the same type — this is the
    invariant that caused the production incident."""

    def test_async_is_context_sync_is_dict(self):
        mod, _ = _load_pams_isolated()
        mod._resolve_ca_file = lambda: _REAL_CA

        ctx = mod._build_async_ssl_context()
        dct = mod._build_sync_ssl_dict()

        assert isinstance(ctx, ssl.SSLContext), "async must be SSLContext"
        assert isinstance(dct, dict), "sync must be dict"
        assert not isinstance(ctx, dict), "async must NOT be dict"
