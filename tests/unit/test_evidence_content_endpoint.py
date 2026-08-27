"""Handler-level tests for ``GET /api/v1/evidence-assets/{asset_id}/content``.

The endpoint serves evidence bytes from App Service instead of handing the
browser a blob SAS URL, so the things worth pinning here are the ones a SAS URL
never had to get right: what goes in the response headers, and what happens when
storage refuses.

Tenant scoping and the 401 are asserted over real HTTP in
``tests/integration/test_evidence_asset_content.py``; this file drives the
handler directly so the header and error-path cases need no database.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.routes.evidence_assets import get_evidence_asset_content
from src.domain.exceptions import NotFoundError
from src.infrastructure.storage import StorageDependencyError, StorageError

PNG_BYTES = b"\x89PNG\r\n\x1a\n fake image payload"


class _Result:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


def _sql(statement) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True})).lower()


def _asset(**overrides):
    defaults = {
        "id": 12,
        "tenant_id": 7,
        "storage_key": "evidence/incident/3/abc_scene.png",
        "original_filename": "scene.png",
        "content_type": "image/png",
        "deleted_at": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _db(asset, statements: list | None = None):
    async def execute(stmt):
        if statements is not None:
            statements.append(stmt)
        return _Result(asset)

    return SimpleNamespace(execute=AsyncMock(side_effect=execute))


def _storage(monkeypatch, *, payload: bytes = PNG_BYTES, raises: Exception | None = None):
    calls: list[str] = []

    async def download(storage_key: str) -> bytes:
        calls.append(storage_key)
        if raises is not None:
            raise raises
        return payload

    monkeypatch.setattr(
        "src.infrastructure.storage.storage_service",
        lambda: SimpleNamespace(download=download),
    )
    return calls


async def _call(monkeypatch, *, asset, disposition="inline", statements=None, **storage_kwargs):
    calls = _storage(monkeypatch, **storage_kwargs)
    response = await get_evidence_asset_content(
        asset_id=getattr(asset, "id", 12),
        db=_db(asset, statements),
        current_user=SimpleNamespace(id=1, tenant_id=7),
        disposition=disposition,
    )
    return response, calls


# ---------------------------------------------------------------------------
# The happy path — bytes, type, and the two headers the browser acts on
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_the_stored_bytes_with_the_stored_content_type(monkeypatch):
    response, calls = await _call(monkeypatch, asset=_asset())

    assert response.body == PNG_BYTES
    assert response.media_type == "image/png"
    assert calls == ["evidence/incident/3/abc_scene.png"], "the asset's own storage_key must be the one read"


@pytest.mark.asyncio
async def test_preview_safe_image_is_served_inline_by_default(monkeypatch):
    response, _ = await _call(monkeypatch, asset=_asset())

    assert response.headers["content-disposition"] == 'inline; filename="scene.png"'


@pytest.mark.asyncio
async def test_attachment_is_honoured_when_asked_for(monkeypatch):
    response, _ = await _call(monkeypatch, asset=_asset(), disposition="attachment")

    assert response.headers["content-disposition"] == 'attachment; filename="scene.png"'


@pytest.mark.asyncio
async def test_non_preview_type_is_forced_to_attachment_even_when_inline_is_asked_for(monkeypatch):
    """Same resolver as signed-url: a Word document never renders in the page."""
    asset = _asset(
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        original_filename="method-statement.docx",
    )

    response, _ = await _call(monkeypatch, asset=asset, disposition="inline")

    assert response.headers["content-disposition"] == 'attachment; filename="method-statement.docx"'


@pytest.mark.asyncio
async def test_the_handler_does_not_set_its_own_cache_control(monkeypatch):
    """Caching is the middleware's job, and it is stricter than this handler.

    ``SecurityHeadersMiddleware`` puts ``no-store, no-cache, must-revalidate`` on
    every ``/api/`` response. A handler value would be overwritten, so setting one
    here would only tell a reader something untrue. The effective header is
    asserted for real in ``tests/integration/test_evidence_asset_content.py``.
    """
    response, _ = await _call(monkeypatch, asset=_asset())

    assert "cache-control" not in response.headers


@pytest.mark.asyncio
async def test_missing_content_type_falls_back_to_octet_stream(monkeypatch):
    response, _ = await _call(monkeypatch, asset=_asset(content_type=None))

    assert response.media_type == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment;")


@pytest.mark.asyncio
async def test_an_awkward_filename_cannot_break_the_response_headers(monkeypatch):
    """A SAS parameter tolerates this; a real response header does not.

    ``original_filename`` is whatever the uploading browser sent. Interpolating it
    raw would raise inside Starlette on a non-Latin-1 name and would let a quote
    close the parameter, so the header must be built rather than formatted.
    """
    asset = _asset(original_filename='sc"ene\r\nX-Injected: 1 — café.png')

    response, _ = await _call(monkeypatch, asset=asset)

    header = response.headers["content-disposition"]
    assert "\r" not in header and "\n" not in header
    assert header.count('"') == 2, f"the quoted filename parameter is not closed exactly once: {header}"
    assert "filename*=UTF-8''" in header, "the real name must survive in the RFC 5987 parameter"
    header.encode("latin-1")  # what Starlette does when it writes the header


# ---------------------------------------------------------------------------
# Not yours, gone, or never there
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_asset_is_a_404_with_the_signed_url_error_code(monkeypatch):
    with pytest.raises(NotFoundError) as exc:
        await _call(monkeypatch, asset=None)

    assert exc.value.http_status == 404
    assert exc.value.code == "ASSET_NOT_FOUND"


@pytest.mark.asyncio
async def test_lookup_is_scoped_to_the_callers_tenant_and_excludes_soft_deletes(monkeypatch):
    """The 404 for another tenant's asset comes from the query, not from a branch.

    Asserting the SQL is what proves a cross-tenant id cannot be distinguished from
    a missing one: the row is never loaded, so there is nothing to leak.
    """
    statements: list = []

    with pytest.raises(NotFoundError):
        await _call(monkeypatch, asset=None, statements=statements)

    sql = _sql(statements[0])
    assert "tenant_id = 7" in sql
    assert "id = 12" in sql
    assert "deleted_at is null" in sql


@pytest.mark.asyncio
async def test_storage_is_never_touched_when_the_asset_is_not_visible(monkeypatch):
    """A 404 must not become a blob read attempt for an id the caller cannot see."""
    calls = _storage(monkeypatch)

    with pytest.raises(NotFoundError):
        await get_evidence_asset_content(
            asset_id=12,
            db=_db(None),
            current_user=SimpleNamespace(id=1, tenant_id=7),
            disposition="inline",
        )

    assert calls == []


# ---------------------------------------------------------------------------
# Storage said no
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_storage_dependency_failure_is_a_503_not_a_404(monkeypatch):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await _call(monkeypatch, asset=_asset(), raises=StorageDependencyError("container missing"))

    assert exc.value.status_code == 503
    assert exc.value.detail["error_code"] == "STORAGE_DEPENDENCY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_unreadable_blob_is_a_502_not_a_404(monkeypatch):
    """The record exists; only the blob behind it could not be read.

    Reporting that as ASSET_NOT_FOUND would send a steward looking for a deleted
    asset instead of a storage fault.
    """
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await _call(monkeypatch, asset=_asset(), raises=StorageError("BlobNotFound"))

    assert exc.value.status_code == 502
    assert exc.value.detail["error_code"] == "STORAGE_DOWNLOAD_FAILED"
