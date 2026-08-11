"""FR-DEDUP-02 — refuse twin external audit runs by external_reference."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.api.schemas.audit import AuditRunCreate
from src.domain.models.audit import AuditStatus
from src.domain.services.external_audit_idempotency import (
    conflict_details_for_run,
    normalize_external_reference,
    _survivor_sort_key,
)


def test_normalize_external_reference_trims_and_casefolds():
    assert normalize_external_reference("  00019685  ") == "00019685"
    assert normalize_external_reference("AbC") == "abc"
    assert normalize_external_reference(None) == ""
    assert normalize_external_reference("  ") == ""


def test_survivor_sort_prefers_completed_scored_runs():
    pending = SimpleNamespace(status=AuditStatus.PENDING_REVIEW, score_percentage=None, id=10)
    completed_low = SimpleNamespace(status=AuditStatus.COMPLETED, score_percentage=90.0, id=20)
    completed_high = SimpleNamespace(status=AuditStatus.COMPLETED, score_percentage=99.0, id=5)
    ranked = sorted([pending, completed_low, completed_high], key=_survivor_sort_key)
    assert ranked[-1] is completed_high


def test_conflict_details_expose_deep_link_fields():
    run = SimpleNamespace(
        id=48,
        reference_number="AUD-2026-0048",
        status=AuditStatus.COMPLETED,
        external_reference="00019685",
    )
    details = conflict_details_for_run(run)
    assert details["existing_run_id"] == 48
    assert details["existing_reference_number"] == "AUD-2026-0048"
    assert details["external_reference"] == "00019685"


def test_achilles_create_requires_external_reference():
    with pytest.raises(ValueError, match="external_reference is required"):
        AuditRunCreate(
            template_id=1,
            external_audit_type="achilles_uvdb",
            source_origin="third_party",
            assurance_scheme="Achilles UVDB",
        )


def test_planet_mark_create_requires_external_reference():
    with pytest.raises(ValueError, match="external_reference is required"):
        AuditRunCreate(
            template_id=1,
            external_audit_type="planet_mark",
            source_origin="certification",
        )


def test_achilles_create_accepts_external_reference():
    payload = AuditRunCreate(
        template_id=1,
        external_audit_type="achilles_uvdb",
        source_origin="third_party",
        assurance_scheme="Achilles UVDB",
        external_reference="00019685",
    )
    assert payload.external_reference == "00019685"


@pytest.mark.anyio
async def test_find_existing_external_audit_run_returns_best_survivor():
    """SQLite-backed lookup: completed scored twin wins over pending twin."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from src.domain.models.audit import AuditRun
    from src.domain.models.base import Base
    from src.domain.services.external_audit_idempotency import find_existing_external_audit_run

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # Minimal table for the columns the lookup touches.
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: AuditRun.__table__.create(sync_conn, checkfirst=True))

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        pending = AuditRun(
            id=17,
            reference_number="AUD-2026-0017",
            template_id=2,
            template_version=1,
            status=AuditStatus.PENDING_REVIEW,
            tenant_id=1,
            external_reference="00019685",
            assurance_scheme="Achilles UVDB",
            title="Achilles 2026 Audit",
        )
        completed = AuditRun(
            id=48,
            reference_number="AUD-2026-0048",
            template_id=2,
            template_version=1,
            status=AuditStatus.COMPLETED,
            score_percentage=99.0,
            tenant_id=1,
            external_reference="00019685",
            assurance_scheme="Achilles UVDB",
            title="Achilles 2026 Audit",
        )
        other = AuditRun(
            id=99,
            reference_number="AUD-2026-0099",
            template_id=2,
            template_version=1,
            status=AuditStatus.COMPLETED,
            tenant_id=1,
            external_reference="OTHER",
            assurance_scheme="Achilles UVDB",
            title="Other",
        )
        db.add_all([pending, completed, other])
        await db.commit()

        found = await find_existing_external_audit_run(
            db,
            tenant_id=1,
            external_reference="00019685",
            assurance_scheme="Achilles UVDB",
        )
        assert found is not None
        assert found.reference_number == "AUD-2026-0048"

        missing = await find_existing_external_audit_run(
            db,
            tenant_id=1,
            external_reference="nope",
        )
        assert missing is None

    await engine.dispose()
