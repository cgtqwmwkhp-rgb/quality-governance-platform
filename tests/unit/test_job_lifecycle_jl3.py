"""JL-3: Job cell links — flag gate, href registry, audit_outcome bi-link."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.api.routes import job_lifecycle as job_lifecycle_routes
from src.api.schemas.job_lifecycle import JobCellLinkCreate
from src.core.config import settings
from src.domain.features.catalogue import CLIENT_FEATURES_BY_KEY
from src.domain.models.job_lifecycle import JobCellLink
from src.domain.services.entity_360.producers.job_lifecycle import JobLifecycleProducer
from src.domain.services.href_registry import audit_finding_href, href_for
from src.domain.services.job_lifecycle_service import resolve_cell_link_href, serialize_cell_link
from src.infrastructure.middleware.tenant_context import RLS_TABLES


def test_job_cell_links_flag_pre_registered_default_off():
    feature = CLIENT_FEATURES_BY_KEY["job_cell_links"]
    assert feature.settings_attr == "job_cell_links_enabled"
    assert settings.job_cell_links_enabled is False


@pytest.mark.asyncio
async def test_cell_links_flag_off_returns_404(monkeypatch):
    monkeypatch.setattr(settings, "job_lifecycle_enabled", True)
    monkeypatch.setattr(settings, "job_cell_links_enabled", False)
    with pytest.raises(HTTPException) as exc_info:
        await job_lifecycle_routes.require_job_cell_links_enabled()
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == job_lifecycle_routes.CELL_LINKS_DISABLED_DETAIL


@pytest.mark.asyncio
async def test_cell_links_flag_on_allows_dependency(monkeypatch):
    monkeypatch.setattr(settings, "job_cell_links_enabled", True)
    await job_lifecycle_routes.require_job_cell_links_enabled()


def test_job_cell_links_table_registered_for_rls():
    assert "job_cell_links" in RLS_TABLES


def test_link_model_stores_structured_refs_not_raw_spa_paths():
    cols = {c.name for c in JobCellLink.__table__.columns}
    assert "kind" in cols
    assert "entity_type" in cols
    assert "entity_id" in cols
    assert "external_url" in cols
    assert "audit_run_id" in cols
    assert "audit_finding_id" in cols
    assert "href" not in cols  # resolved via href_registry at read time


def test_resolve_app_and_audit_hrefs_use_registry_only():
    app = SimpleNamespace(
        kind="app",
        entity_type="document",
        entity_id=42,
        external_url=None,
        audit_run_id=None,
        audit_finding_id=None,
    )
    assert resolve_cell_link_href(app) == href_for("document", 42)

    audit = SimpleNamespace(
        kind="audit_outcome",
        entity_type=None,
        entity_id=None,
        external_url=None,
        audit_run_id=12,
        audit_finding_id=88,
    )
    assert resolve_cell_link_href(audit) == audit_finding_href(run_id=12, finding_id=88)

    external = SimpleNamespace(
        kind="external",
        entity_type=None,
        entity_id=None,
        external_url="https://example.test/portal",
        audit_run_id=None,
        audit_finding_id=None,
    )
    assert resolve_cell_link_href(external) == "https://example.test/portal"


def test_create_schema_rejects_mismatched_kind_fields():
    with pytest.raises(ValidationError):
        JobCellLinkCreate(kind="app", label="x", external_url="https://example.test")
    with pytest.raises(ValidationError):
        JobCellLinkCreate(kind="external", label="x", entity_type="document", entity_id=1)
    with pytest.raises(ValidationError):
        JobCellLinkCreate(kind="audit_outcome", label="x", audit_run_id=1)
    JobCellLinkCreate(kind="app", label="Doc", entity_type="document", entity_id=7)
    JobCellLinkCreate(kind="external", label="Portal", external_url="https://example.test/a")
    JobCellLinkCreate(
        kind="audit_outcome",
        label="NC",
        audit_run_id=12,
        audit_finding_id=88,
    )


def test_serialize_cell_link_includes_registry_href():
    row = SimpleNamespace(
        id=1,
        tenant_id=1,
        cell_id=2,
        kind="app",
        label="Policy",
        entity_type="document",
        entity_id=9,
        external_url=None,
        audit_run_id=None,
        audit_finding_id=None,
        sort_order=0,
        created_at="t0",
        updated_at="t1",
    )
    payload = serialize_cell_link(row)
    assert payload["href"] == href_for("document", 9)
    assert payload["kind"] == "app"


def test_job_producer_supports_audit_finding_bidirectional():
    producer = JobLifecycleProducer()
    assert producer.supports("audit_finding")
    assert producer.supports("job_step")
    assert producer.supports("document")


@pytest.mark.asyncio
async def test_job_producer_audit_finding_emits_both_lists_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "job_cell_links_enabled", False)
    producer = JobLifecycleProducer()
    db = SimpleNamespace(execute=AsyncMock())
    result = await producer.produce(
        db=db,
        tenant_id=1,
        entity_type="audit_finding",
        entity_id=88,
        user=SimpleNamespace(is_superuser=True),
    )
    assert result.status == "ok"
    assert result.upstream == []
    assert result.downstream == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_job_producer_audit_finding_bi_link_when_flag_on(monkeypatch):
    monkeypatch.setattr(settings, "job_cell_links_enabled", True)
    producer = JobLifecycleProducer()

    step = SimpleNamespace(id=3, name="Deliver", code="deliver", is_active=True)
    cell = SimpleNamespace(id=5, step_id=3, deleted_at=None)
    link = SimpleNamespace(
        kind="audit_outcome",
        audit_finding_id=88,
        label="NC",
    )

    class _Result:
        def all(self):
            return [(link, cell, step)]

    db = SimpleNamespace(execute=AsyncMock(return_value=_Result()))
    result = await producer.produce(
        db=db,
        tenant_id=1,
        entity_type="audit_finding",
        entity_id=88,
        user=SimpleNamespace(is_superuser=True),
    )
    assert result.status == "ok"
    assert result.upstream == []
    assert len(result.downstream) == 1
    hop = result.downstream[0]
    assert hop["source_type"] == "job_step"
    assert hop["source_id"] == 3
    assert hop["href"] == href_for("job_step", 3)
    assert hop["relation"] == "job_cell_link"
    assert hop["origin"] == "job"
