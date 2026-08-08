"""JL-1: Job Lifecycle axes — models, flag gate, authz, Entity360 producer."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.routes import job_lifecycle as job_lifecycle_routes
from src.core.config import settings
from src.domain.authz.catalogue import ADMIN_ROLE_PERMISSIONS, ENFORCED_PERMISSIONS
from src.domain.features.catalogue import CLIENT_FEATURES_BY_KEY
from src.domain.models.job_lifecycle import JobCell, JobCellDocument, JobLane, JobStep, JobType
from src.domain.services.entity_360.permissions import HOP_READ_PERMISSIONS
from src.domain.services.entity_360.producers.job_lifecycle import JobLifecycleProducer
from src.domain.services.entity_360.registry import all_producers, ensure_default_producers, reset_producers
from src.infrastructure.middleware.tenant_context import RLS_TABLES


def test_job_lifecycle_flag_pre_registered_default_off():
    feature = CLIENT_FEATURES_BY_KEY["job_lifecycle"]
    assert feature.settings_attr == "job_lifecycle_enabled"
    assert feature.required_permission == "job:read"
    assert settings.job_lifecycle_enabled is False


def test_job_authz_tokens_enforced_and_in_admin_grant():
    assert "job:read" in ENFORCED_PERMISSIONS
    assert "job:author" in ENFORCED_PERMISSIONS
    assert "job:read" in ADMIN_ROLE_PERMISSIONS
    assert "job:author" in ADMIN_ROLE_PERMISSIONS
    assert len(ADMIN_ROLE_PERMISSIONS) == 84


def test_job_step_hop_permission_uses_job_read():
    assert HOP_READ_PERMISSIONS["job_step"] == "job:read"


def test_jl_tables_registered_for_rls():
    for table in (
        "job_types",
        "job_lanes",
        "job_steps",
        "job_cells",
        "job_cell_documents",
        "job_cell_links",
    ):
        assert table in RLS_TABLES


def test_axis_models_use_code_identity_not_lookup_or_department():
    """ADR-0022: identity is JL code; no LookupOption / department columns."""
    for model in (JobType, JobLane, JobStep):
        cols = {c.name for c in model.__table__.columns}
        assert "code" in cols
        assert "name" in cols
        assert "lookup_option_id" not in cols
        assert "department" not in cols
        assert "org_unit_id" not in cols


def test_cell_holds_document_refs_only_via_junction():
    cell_cols = {c.name for c in JobCell.__table__.columns}
    assert "library_document_id" not in cell_cols  # membership is junction, not JSON body
    junction_cols = {c.name for c in JobCellDocument.__table__.columns}
    assert "library_document_id" in junction_cols
    assert "cell_id" in junction_cols


@pytest.mark.asyncio
async def test_flag_off_returns_404(monkeypatch):
    monkeypatch.setattr(settings, "job_lifecycle_enabled", False)
    with pytest.raises(HTTPException) as exc_info:
        await job_lifecycle_routes.require_job_lifecycle_enabled()
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == job_lifecycle_routes.DISABLED_DETAIL


@pytest.mark.asyncio
async def test_flag_on_allows_dependency(monkeypatch):
    monkeypatch.setattr(settings, "job_lifecycle_enabled", True)
    await job_lifecycle_routes.require_job_lifecycle_enabled()


def test_job_producer_registers_bidirectional_day_one():
    reset_producers()
    ensure_default_producers()
    producers = list(all_producers())
    origins = {p.origin for p in producers}
    assert "job" in origins
    job = next(p for p in producers if p.origin == "job")
    assert isinstance(job, JobLifecycleProducer)
    assert job.supports("document")
    assert job.supports("job_step")
    assert job.supports("audit_finding")


@pytest.mark.asyncio
async def test_job_producer_emits_both_direction_lists_when_empty():
    producer = JobLifecycleProducer()

    class _Result:
        def all(self):
            return []

    db = SimpleNamespace(execute=AsyncMock(return_value=_Result()))
    for entity_type, entity_id in (("document", 10), ("job_step", 3)):
        result = await producer.produce(
            db=db,
            tenant_id=1,
            entity_type=entity_type,
            entity_id=entity_id,
            user=SimpleNamespace(is_superuser=True, has_permission=lambda _p: True),
        )
        assert result.status == "ok"
        assert isinstance(result.upstream, list)
        assert isinstance(result.downstream, list)
        assert result.origin == "job"
