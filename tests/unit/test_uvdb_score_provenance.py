"""PX-255 — UVDB score display provenance and absent-score handling.

The Run021 defect report diagnosed PX-255 as a scoring-model defect. It is not:
the scoring arithmetic is correct. The defect is in how scores are presented —
an imported score was indistinguishable from a calculated one, per-section
imported scores could be dropped or attributed to the wrong protocol section,
and an absent score could surface as a real-looking 0.

These tests pin the corrected behaviour:
  * an imported score is returned and labelled as imported;
  * a calculated score is still returned and labelled as calculated;
  * an absent score is returned as absent — never 0, never 100.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.routes.uvdb import get_audit, get_section_scores, get_uvdb_dashboard, list_audits
from src.domain.models.audit import AuditRun
from src.domain.models.external_audit_import import ExternalAuditImportJob
from src.domain.models.uvdb_achilles import UVDBAudit
from src.domain.services.uvdb_service import (
    SCORE_SOURCE_CALCULATED,
    SCORE_SOURCE_IMPORTED,
    SCORE_SOURCE_UNKNOWN,
    average_percentage,
    build_section_title_index,
    coerce_score,
    derive_percentage,
    match_protocol_section,
    normalise_section_score,
    resolve_provenance,
    resolve_score_source,
)
from src.domain.uvdb.protocol_b2_v118 import UVDB_B2_SECTIONS

TENANT_ID = 1
VALID_SECTIONS = [str(section["number"]) for section in UVDB_B2_SECTIONS]


# ---------------------------------------------------------------- pure helpers


class TestScoreSourceResolution:
    def test_score_from_an_import_job_is_labelled_imported(self):
        assert resolve_score_source(93.0, import_job_id=72) == SCORE_SOURCE_IMPORTED

    def test_score_without_an_import_job_is_labelled_calculated(self):
        assert resolve_score_source(93.0, import_job_id=None) == SCORE_SOURCE_CALCULATED

    def test_absent_score_has_no_provenance(self):
        assert resolve_score_source(None, import_job_id=72) is None
        assert resolve_score_source(None, import_job_id=None) is None

    def test_zero_is_a_real_score_and_keeps_its_provenance(self):
        # 0.0 is falsy; it must not be mistaken for "no score".
        assert resolve_score_source(0.0, import_job_id=72) == SCORE_SOURCE_IMPORTED
        assert resolve_score_source(0.0, import_job_id=None) == SCORE_SOURCE_CALCULATED

    def test_unresolvable_linkage_reports_unknown_not_calculated(self):
        # Claiming "calculated" when we could not read the import linkage would
        # assert provenance we do not have.
        assert resolve_score_source(93.0, import_job_id=None, provenance_resolved=False) == SCORE_SOURCE_UNKNOWN
        assert resolve_provenance(import_job_id=72, provenance_resolved=False) == SCORE_SOURCE_UNKNOWN


class TestAbsentScoresNeverBecomeZeroOrFull:
    def test_empty_denominator_yields_none_not_one_hundred(self):
        # The repo-wide `if total else 100.0` anti-pattern, refused here.
        assert derive_percentage(0.0, 0.0) is None
        assert derive_percentage(None, 0.0) is None
        assert derive_percentage(5.0, None) is None
        assert derive_percentage(5.0, -1.0) is None

    def test_real_denominator_yields_the_real_percentage(self):
        assert derive_percentage(14.0, 15.0) == 93.3
        assert derive_percentage(0.0, 15.0) == 0.0

    def test_average_of_nothing_is_none(self):
        assert average_percentage([]) is None
        assert average_percentage([None, None]) is None

    def test_average_ignores_unscored_entries(self):
        assert average_percentage([90.0, None, 80.0]) == 85.0

    @pytest.mark.parametrize(
        "raw,expected",
        [
            (None, None),
            ("", None),
            ("   ", None),
            ("not a number", None),
            (True, None),
            (0, 0.0),
            ("0", 0.0),
            (93, 93.0),
            ("93.5", 93.5),
            ("93%", 93.0),
        ],
    )
    def test_score_coercion_preserves_absence(self, raw, expected):
        assert coerce_score(raw) == expected

    def test_section_entry_with_no_scores_stays_absent(self):
        entry = normalise_section_score(
            {"label": "Waste Management"},
            audit_reference="UVDB-2026-0001",
            score_source=SCORE_SOURCE_IMPORTED,
        )
        assert entry["score"] is None
        assert entry["max_score"] is None
        assert entry["percentage"] is None
        assert entry["score_source"] == SCORE_SOURCE_IMPORTED

    def test_section_entry_with_zero_max_score_does_not_report_full_marks(self):
        entry = normalise_section_score(
            {"label": "Section 3", "score": 0, "max_score": 0},
            audit_reference="UVDB-2026-0001",
            score_source=SCORE_SOURCE_IMPORTED,
        )
        assert entry["percentage"] is None

    def test_section_entry_derives_a_missing_percentage(self):
        entry = normalise_section_score(
            {"label": "Section 3", "score": 14, "max_score": 15},
            audit_reference="UVDB-2026-0001",
            score_source=SCORE_SOURCE_IMPORTED,
        )
        assert entry["percentage"] == 93.3


class TestProtocolSectionMatching:
    """The imported label -> protocol section mapping that was hiding scores."""

    def test_explicit_section_prefix_matches(self):
        assert match_protocol_section("Section 3 Health and Safety", valid_section_numbers=VALID_SECTIONS) == "3"
        assert match_protocol_section("SECTION 12", valid_section_numbers=VALID_SECTIONS) == "12"

    def test_iso_style_label_is_not_mistaken_for_a_section_number(self):
        # The old regex pulled "45" out of "ISO 45001" and filed the score under
        # a section number that does not exist, so the score never rendered.
        assert match_protocol_section("ISO 45001 alignment", valid_section_numbers=VALID_SECTIONS) is None
        assert match_protocol_section("Section 45001 alignment", valid_section_numbers=VALID_SECTIONS) is None

    def test_unmatchable_label_is_not_guessed_positionally(self):
        # The old fallback used the entry's list position, silently attributing
        # a real score to whichever section happened to share that index.
        assert match_protocol_section("Housekeeping observations", valid_section_numbers=VALID_SECTIONS) is None
        assert match_protocol_section("", valid_section_numbers=VALID_SECTIONS) is None

    def test_exact_protocol_title_matches(self):
        index = build_section_title_index(UVDB_B2_SECTIONS)
        assert (
            match_protocol_section(
                "Health and Safety Policy and Leadership",
                valid_section_numbers=VALID_SECTIONS,
                title_index=index,
            )
            == "3"
        )

    def test_title_index_excludes_ambiguous_titles(self):
        index = build_section_title_index(
            [
                {"number": "1", "title": "Shared Title"},
                {"number": "2", "title": "Shared Title"},
                {"number": "3", "title": "Unique Title"},
            ]
        )
        assert "shared title" not in index
        assert index["unique title"] == "3"


# ------------------------------------------------------------- route behaviour


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(UVDBAudit.__table__.create)
        await conn.run_sync(AuditRun.__table__.create)
        await conn.run_sync(ExternalAuditImportJob.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


def _user():
    return SimpleNamespace(tenant_id=TENANT_ID)


async def _list(db):
    """Call list_audits with resolved defaults (FastAPI is not in the loop here)."""
    return await list_audits(
        db,
        _user(),
        status=None,
        company_name=None,
        audit_type=None,
        date_from=None,
        date_to=None,
        min_score=None,
        max_score=None,
        search=None,
        skip=0,
        limit=50,
    )


async def _add_uvdb_audit(db, *, reference, percentage_score, section_scores=None, audit_date="2026-03-20"):
    audit = UVDBAudit(
        tenant_id=TENANT_ID,
        audit_reference=reference,
        company_name="Plantexpand Limited",
        audit_type="B2",
        audit_date=datetime.fromisoformat(audit_date) if audit_date else None,
        status="completed",
        percentage_score=percentage_score,
        total_score=percentage_score,
        max_possible_score=100.0 if percentage_score is not None else None,
        section_scores=section_scores,
    )
    db.add(audit)
    await db.flush()
    return audit


async def _link_import_job(db, *, reference, source_filename="achilles-b2.pdf", tenant_id=TENANT_ID):
    """Attach a promoted external import job to a UVDB audit reference."""
    run = AuditRun(
        tenant_id=tenant_id,
        template_id=1,
        reference_number=reference,
        title="Imported Achilles B2 audit",
    )
    db.add(run)
    await db.flush()
    job = ExternalAuditImportJob(
        tenant_id=tenant_id,
        audit_run_id=run.id,
        reference_number=f"EAI-{reference}",
        source_document_asset_id=901,
        source_checksum_sha256=f"sha-{reference}",
        idempotency_key=f"idem-{reference}",
        source_filename=source_filename,
    )
    db.add(job)
    await db.flush()
    return run, job


class TestListAuditsProvenance:
    async def test_imported_score_is_returned_and_labelled_imported(self, session_factory):
        async with session_factory() as db:
            await _add_uvdb_audit(db, reference="UVDB-2026-0001", percentage_score=93.0)
            run, job = await _link_import_job(db, reference="UVDB-2026-0001")

            payload = await _list(db)

        row = payload["audits"][0]
        assert row["percentage_score"] == 93.0
        assert row["score_source"] == SCORE_SOURCE_IMPORTED
        assert row["audit_run_id"] == run.id
        assert row["import_job_id"] == job.id

    async def test_calculated_score_is_returned_and_labelled_calculated(self, session_factory):
        async with session_factory() as db:
            await _add_uvdb_audit(db, reference="UVDB-2026-0002", percentage_score=88.0)

            payload = await _list(db)

        row = payload["audits"][0]
        assert row["percentage_score"] == 88.0
        assert row["score_source"] == SCORE_SOURCE_CALCULATED
        assert row["import_job_id"] is None

    async def test_import_link_from_another_tenant_is_not_used(self, session_factory):
        async with session_factory() as db:
            await _add_uvdb_audit(db, reference="UVDB-2026-0001", percentage_score=93.0)
            await _link_import_job(db, reference="UVDB-2026-0001", tenant_id=TENANT_ID + 1)

            payload = await _list(db)

        row = payload["audits"][0]
        # The reference collides across tenants; the other tenant's run and job
        # identifiers must not be handed to this caller.
        assert row["audit_run_id"] is None
        assert row["import_job_id"] is None
        assert row["score_source"] == SCORE_SOURCE_CALCULATED

    async def test_absent_score_is_absent_not_zero(self, session_factory):
        async with session_factory() as db:
            await _add_uvdb_audit(db, reference="UVDB-2026-0003", percentage_score=None)

            payload = await _list(db)

        row = payload["audits"][0]
        assert row["percentage_score"] is None
        assert row["percentage_score"] != 0
        assert row["score_source"] is None


class TestGetAuditProvenance:
    async def test_imported_detail_carries_provenance_and_source_document(self, session_factory):
        async with session_factory() as db:
            audit = await _add_uvdb_audit(
                db,
                reference="UVDB-2026-0001",
                percentage_score=93.0,
                section_scores={"sections": [{"label": "Section 3", "score": 14, "max_score": 15}]},
            )
            run, job = await _link_import_job(db, reference="UVDB-2026-0001")

            payload = await get_audit(audit.id, db, _user())

        assert payload["percentage_score"] == 93.0
        assert payload["score_source"] == SCORE_SOURCE_IMPORTED
        assert payload["audit_run_id"] == run.id
        assert payload["import_job_id"] == job.id
        assert payload["source_filename"] == "achilles-b2.pdf"
        assert payload["score_breakdown"][0]["score_source"] == SCORE_SOURCE_IMPORTED
        assert payload["score_breakdown"][0]["percentage"] == 93.3

    async def test_calculated_detail_is_labelled_calculated(self, session_factory):
        async with session_factory() as db:
            audit = await _add_uvdb_audit(db, reference="UVDB-2026-0002", percentage_score=88.0)

            payload = await get_audit(audit.id, db, _user())

        assert payload["score_source"] == SCORE_SOURCE_CALCULATED
        assert payload["import_job_id"] is None

    async def test_unscored_detail_reports_no_score_and_no_provenance(self, session_factory):
        async with session_factory() as db:
            audit = await _add_uvdb_audit(db, reference="UVDB-2026-0003", percentage_score=None)

            payload = await get_audit(audit.id, db, _user())

        assert payload["percentage_score"] is None
        assert payload["score_source"] is None

    async def test_breakdown_entry_without_scores_stays_absent(self, session_factory):
        async with session_factory() as db:
            audit = await _add_uvdb_audit(
                db,
                reference="UVDB-2026-0004",
                percentage_score=70.0,
                section_scores={"sections": [{"label": "Section 5", "score": None, "max_score": 0}]},
            )

            payload = await get_audit(audit.id, db, _user())

        entry = payload["score_breakdown"][0]
        assert entry["score"] is None
        assert entry["percentage"] is None


class TestSectionScoresProvenance:
    async def test_imported_section_scores_are_returned_and_labelled(self, session_factory):
        async with session_factory() as db:
            await _add_uvdb_audit(
                db,
                reference="UVDB-2026-0001",
                percentage_score=93.0,
                section_scores={
                    "sections": [
                        {"label": "Section 3 Health and Safety", "score": 14, "max_score": 15, "percentage": 93.3},
                        {"label": "Health and Safety Policy and Leadership", "score": 9, "max_score": 12},
                    ]
                },
            )
            await _link_import_job(db, reference="UVDB-2026-0001")

            payload = await get_section_scores(db, _user())

        assert payload["score_source"] == SCORE_SOURCE_IMPORTED
        assert payload["sections"]["3"]["percentage"] == 93.3
        assert payload["sections"]["3"]["score_source"] == SCORE_SOURCE_IMPORTED
        # The title-matched duplicate also resolves to section 3, so rather than
        # overwriting it silently the second entry is surfaced as unmapped.
        assert [entry["label"] for entry in payload["unmapped_sections"]] == ["Health and Safety Policy and Leadership"]

    async def test_label_that_cannot_be_matched_is_surfaced_not_dropped(self, session_factory):
        async with session_factory() as db:
            await _add_uvdb_audit(
                db,
                reference="UVDB-2026-0001",
                percentage_score=93.0,
                section_scores={"sections": [{"label": "ISO 45001 alignment", "score": 8, "max_score": 10}]},
            )
            await _link_import_job(db, reference="UVDB-2026-0001")

            payload = await get_section_scores(db, _user())

        # Previously "45" was extracted as the section number, filing the score
        # under a section that does not exist so it never rendered anywhere.
        assert payload["sections"] == {}
        assert payload["unmapped_sections"][0]["label"] == "ISO 45001 alignment"
        assert payload["unmapped_sections"][0]["percentage"] == 80.0
        assert payload["unmapped_sections"][0]["score_source"] == SCORE_SOURCE_IMPORTED

    async def test_section_scores_of_a_non_imported_audit_are_labelled_calculated(self, session_factory):
        async with session_factory() as db:
            await _add_uvdb_audit(
                db,
                reference="UVDB-2026-0002",
                percentage_score=88.0,
                section_scores={"sections": [{"label": "Section 1", "score": 18, "max_score": 21}]},
            )

            payload = await get_section_scores(db, _user())

        assert payload["score_source"] == SCORE_SOURCE_CALCULATED
        assert payload["sections"]["1"]["score_source"] == SCORE_SOURCE_CALCULATED

    async def test_missing_section_values_are_absent_not_zero(self, session_factory):
        async with session_factory() as db:
            await _add_uvdb_audit(
                db,
                reference="UVDB-2026-0003",
                percentage_score=None,
                section_scores={"sections": [{"label": "Section 2"}]},
            )

            payload = await get_section_scores(db, _user())

        entry = payload["sections"]["2"]
        assert entry["score"] is None
        assert entry["max_score"] is None
        assert entry["percentage"] is None

    async def test_no_completed_audit_returns_an_empty_shape(self, session_factory):
        async with session_factory() as db:
            payload = await get_section_scores(db, _user())

        assert payload["sections"] == {}
        assert payload["unmapped_sections"] == []
        assert payload["score_source"] is None


class TestDashboardAverage:
    async def test_completed_audits_with_no_scores_report_no_average(self, session_factory):
        async with session_factory() as db:
            await _add_uvdb_audit(db, reference="UVDB-2026-0001", percentage_score=None)
            await _add_uvdb_audit(db, reference="UVDB-2026-0002", percentage_score=None)

            payload = await get_uvdb_dashboard(db, _user())

        summary = payload["summary"]
        assert summary["completed_audits"] == 2
        # Not 0, and not 100 — nothing has been scored.
        assert summary["average_score"] is None
        assert summary["scored_audits"] == 0

    async def test_average_is_computed_over_scored_audits_only(self, session_factory):
        async with session_factory() as db:
            await _add_uvdb_audit(db, reference="UVDB-2026-0001", percentage_score=90.0)
            await _add_uvdb_audit(db, reference="UVDB-2026-0002", percentage_score=80.0)
            await _add_uvdb_audit(db, reference="UVDB-2026-0003", percentage_score=None)

            payload = await get_uvdb_dashboard(db, _user())

        summary = payload["summary"]
        assert summary["average_score"] == 85.0
        assert summary["scored_audits"] == 2
