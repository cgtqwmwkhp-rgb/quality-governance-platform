"""absolute_href — email-safe SPA URL resolution."""

from __future__ import annotations

from src.domain.services.href_registry import absolute_href


def test_absolute_href_joins_frontend_base(monkeypatch):
    from src.core import config

    monkeypatch.setattr(config.settings, "frontend_url", "https://app.example.test/")
    assert absolute_href("/compliance-schedule/3") == "https://app.example.test/compliance-schedule/3"


def test_absolute_href_passes_through_https():
    assert absolute_href("https://app.example.test/x") == "https://app.example.test/x"


def test_absolute_href_rejects_unsafe_schemes():
    assert absolute_href("javascript:alert(1)") is None
    assert absolute_href("data:text/html,hi") is None
    assert absolute_href("example.com/path") is None
    assert absolute_href("") is None
    assert absolute_href(None) is None
