"""Tests for the FR-DEDUP-01 duplicate audit purge and register scanner (Run027).

The refusals *are* the product here. A script that deletes audit records is only as
good as the things it declines to do, so each refusal is proved by building the
condition that should trigger it and observing the refusal — never by asserting that
a branch exists in the source.

Everything runs against a real SQLite database whose DDL carries the same
``ON DELETE`` rules as production: ``CASCADE`` on ``audit_responses``,
``audit_findings`` and the import tables, ``SET NULL`` on ``job_cell_links``, and
crucially **no clause at all** on ``external_audit_records.audit_run_id``. That last
one is the reason this script exists in the shape it does, so it is reproduced rather
than described: the foreign keys are reflected from this schema exactly as they are
from PostgreSQL.

Nothing here imports the FastAPI app. The ops scripts do not need it.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from scripts.ops.run027 import inventory_duplicate_registers as scanner
from scripts.ops.run027 import purge_duplicate_audit_runs as purge
from scripts.ops.run027._closure import AUDIT_RUN_CHILD_DISPOSITIONS, Disposition, descendant_closure
from scripts.ops.run027._duplicates import LIFECYCLE_IDENTITY_COLUMNS, MIN_IDENTITY_COLUMNS, REGISTERS
from scripts.ops.run027._soft_links import SOFT_LINK_DISPOSITIONS
from scripts.ops.run027.purge_duplicate_audit_runs import FR_DEDUP_01_REFERENCES, FR_DEDUP_01_TENANT
from scripts.ops.run027.purge_duplicate_audit_runs import main as purge_main
from scripts.ops.run027.purge_duplicate_audit_runs import plan

# --------------------------------------------------------------------------- #
# Production facts, reproduced. The twins, the survivor, and the tenant.
# --------------------------------------------------------------------------- #

#: The audit that survives: the earlier import that was subsequently updated.
SURVIVOR_ID = 31
SURVIVOR_REFERENCE = "AUD-2026-0031"

#: The two re-imports FR-DEDUP-01 authorises removing.
TWIN_IDS = (43, 48)

#: Shared by all three rows. This is what makes them the same audit.
TWIN_TITLE = "B2 Audit - 2026-02-20T00:00:00 - Kevin Game"
TWIN_AUDITOR = "Kevin Game"
TWIN_SCORE = 97.7

#: Highest audit reference suffix seeded. Above the twins, so the default fixture is
#: *not* in reference-reuse danger and the clean path can be tested; the hazard has
#: its own fixture.
DEFAULT_TOP_SUFFIX = 60

_SCHEMA: tuple[str, ...] = (
    "CREATE TABLE tenants (id INTEGER PRIMARY KEY, name VARCHAR(200))",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255), tenant_id INTEGER REFERENCES tenants(id))",
    "CREATE TABLE audit_templates (id INTEGER PRIMARY KEY, name VARCHAR(200), tenant_id INTEGER)",
    "CREATE TABLE evidence_assets (id INTEGER PRIMARY KEY, tenant_id INTEGER)",
    "CREATE TABLE job_cells (id INTEGER PRIMARY KEY, tenant_id INTEGER)",
    "CREATE TABLE job_types (id INTEGER PRIMARY KEY, tenant_id INTEGER)",
    """
    CREATE TABLE audit_runs (
        id INTEGER PRIMARY KEY,
        reference_number VARCHAR(50) UNIQUE,
        template_id INTEGER NOT NULL REFERENCES audit_templates(id),
        title VARCHAR(300),
        status VARCHAR(50),
        source_origin VARCHAR(50),
        assurance_scheme VARCHAR(100),
        external_auditor_name VARCHAR(255),
        external_reference VARCHAR(100),
        external_body_name VARCHAR(255),
        source_document_label VARCHAR(255),
        score_percentage FLOAT,
        scheduled_date DATETIME,
        completed_at DATETIME,
        created_at DATETIME,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id)
    )
    """,
    "CREATE TABLE audit_questions (id INTEGER PRIMARY KEY, question_text TEXT, tenant_id INTEGER)",
    """
    CREATE TABLE audit_responses (
        id INTEGER PRIMARY KEY,
        run_id INTEGER NOT NULL,
        question_id INTEGER,
        response_value VARCHAR(500),
        notes TEXT,
        tenant_id INTEGER,
        FOREIGN KEY (run_id) REFERENCES audit_runs(id) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES audit_questions(id)
    )
    """,
    """
    CREATE TABLE audit_findings (
        id INTEGER PRIMARY KEY,
        run_id INTEGER NOT NULL,
        reference_number VARCHAR(50) UNIQUE,
        title VARCHAR(300),
        description TEXT,
        severity VARCHAR(50),
        finding_type VARCHAR(50),
        status VARCHAR(50),
        tenant_id INTEGER,
        FOREIGN KEY (run_id) REFERENCES audit_runs(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE risks_v2 (
        id INTEGER PRIMARY KEY,
        reference VARCHAR(50) UNIQUE,
        title VARCHAR(300),
        category VARCHAR(100),
        description TEXT,
        status VARCHAR(50),
        created_at DATETIME,
        tenant_id INTEGER
    )
    """,
    # Junction. CASCADE from both sides, and it has its own single-column key, so
    # its rows are individually addressable.
    """
    CREATE TABLE audit_finding_risks (
        id INTEGER PRIMARY KEY,
        audit_finding_id INTEGER NOT NULL,
        risk_id INTEGER NOT NULL,
        created_at DATETIME,
        FOREIGN KEY (audit_finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE,
        FOREIGN KEY (risk_id) REFERENCES risks_v2(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE external_audit_import_jobs (
        id INTEGER PRIMARY KEY,
        audit_run_id INTEGER NOT NULL,
        source_document_asset_id INTEGER NOT NULL,
        tenant_id INTEGER NOT NULL,
        reference_number VARCHAR(50) UNIQUE,
        status VARCHAR(50),
        source_checksum_sha256 VARCHAR(64),
        idempotency_key VARCHAR(255) UNIQUE,
        FOREIGN KEY (audit_run_id) REFERENCES audit_runs(id) ON DELETE CASCADE,
        FOREIGN KEY (source_document_asset_id) REFERENCES evidence_assets(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE external_audit_import_drafts (
        id INTEGER PRIMARY KEY,
        import_job_id INTEGER NOT NULL,
        audit_run_id INTEGER NOT NULL,
        promoted_finding_id INTEGER,
        tenant_id INTEGER,
        status VARCHAR(50),
        title VARCHAR(300),
        description TEXT,
        FOREIGN KEY (import_job_id) REFERENCES external_audit_import_jobs(id) ON DELETE CASCADE,
        FOREIGN KEY (audit_run_id) REFERENCES audit_runs(id) ON DELETE CASCADE,
        FOREIGN KEY (promoted_finding_id) REFERENCES audit_findings(id)
    )
    """,
    # The whole reason the purge cannot rely on cascades: neither foreign key here
    # carries an ON DELETE clause, so both are NO ACTION and both would block.
    """
    CREATE TABLE external_audit_records (
        id INTEGER PRIMARY KEY,
        tenant_id INTEGER,
        scheme VARCHAR(50),
        audit_run_id INTEGER,
        import_job_id INTEGER,
        company_name VARCHAR(200),
        score_percentage FLOAT,
        status VARCHAR(30),
        FOREIGN KEY (audit_run_id) REFERENCES audit_runs(id),
        FOREIGN KEY (import_job_id) REFERENCES external_audit_import_jobs(id)
    )
    """,
    """
    CREATE TABLE job_cell_links (
        id INTEGER PRIMARY KEY,
        tenant_id INTEGER NOT NULL,
        cell_id INTEGER NOT NULL,
        kind VARCHAR(32),
        label VARCHAR(300),
        entity_type VARCHAR(64),
        entity_id INTEGER,
        audit_run_id INTEGER,
        audit_finding_id INTEGER,
        target_job_type_id INTEGER,
        sort_order INTEGER DEFAULT 0,
        FOREIGN KEY (cell_id) REFERENCES job_cells(id) ON DELETE CASCADE,
        FOREIGN KEY (audit_run_id) REFERENCES audit_runs(id) ON DELETE SET NULL,
        FOREIGN KEY (audit_finding_id) REFERENCES audit_findings(id) ON DELETE SET NULL,
        FOREIGN KEY (target_job_type_id) REFERENCES job_types(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE notifications (
        id INTEGER PRIMARY KEY,
        tenant_id INTEGER,
        user_id INTEGER NOT NULL REFERENCES users(id),
        title VARCHAR(255),
        message TEXT,
        entity_type VARCHAR(50),
        entity_id VARCHAR(36)
    )
    """,
    """
    CREATE TABLE assignments (
        id INTEGER PRIMARY KEY,
        tenant_id INTEGER,
        entity_type VARCHAR(50) NOT NULL,
        entity_id VARCHAR(36) NOT NULL,
        assigned_to_user_id INTEGER NOT NULL REFERENCES users(id),
        assigned_by_user_id INTEGER NOT NULL REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE capa_actions (
        id INTEGER PRIMARY KEY,
        tenant_id INTEGER NOT NULL,
        reference_number VARCHAR(50) UNIQUE NOT NULL,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        capa_type VARCHAR(50),
        status VARCHAR(50),
        source_type VARCHAR(50),
        source_id INTEGER,
        due_date DATETIME,
        created_at DATETIME
    )
    """,
    # Mirrors PostgreSQL migration d3e4f5a6b7c8. SQLite does not get that index from
    # Alembic (dialect-gated), so the fixture creates it or CAPA collision tests would
    # pass against a database incapable of failing.
    """
    CREATE UNIQUE INDEX uq_capa_actions_tenant_audit_finding_source
    ON capa_actions (tenant_id, source_id)
    WHERE source_type = 'audit_finding' AND source_id IS NOT NULL
    """,
    """
    CREATE TABLE compliance_evidence_links (
        id INTEGER PRIMARY KEY,
        tenant_id INTEGER NOT NULL,
        entity_type VARCHAR(50) NOT NULL,
        entity_id VARCHAR(100) NOT NULL,
        clause_id VARCHAR(50) NOT NULL,
        cover_kind VARCHAR(20) NOT NULL DEFAULT 'evidences',
        signal_type VARCHAR(30),
        status VARCHAR(30),
        linked_by VARCHAR(20),
        notes TEXT,
        deleted_at DATETIME,
        created_at DATETIME,
        updated_at DATETIME
    )
    """,
    """
    CREATE UNIQUE INDEX ux_cel_tenant_entity_clause_cover_live
    ON compliance_evidence_links (tenant_id, entity_type, entity_id, clause_id, cover_kind)
    WHERE deleted_at IS NULL
    """,
    """
    CREATE TABLE audit_log_entries (
        id INTEGER PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id),
        sequence INTEGER NOT NULL,
        entry_hash VARCHAR(64) NOT NULL UNIQUE,
        previous_hash VARCHAR(64) NOT NULL,
        entity_type VARCHAR(100) NOT NULL,
        entity_id VARCHAR(100) NOT NULL,
        entity_name VARCHAR(255),
        action VARCHAR(50) NOT NULL,
        action_category VARCHAR(50) NOT NULL,
        old_values JSON,
        new_values JSON,
        changed_fields JSON,
        user_id INTEGER REFERENCES users(id),
        user_email VARCHAR(255),
        user_name VARCHAR(255),
        user_role VARCHAR(50),
        ip_address VARCHAR(45),
        user_agent VARCHAR(500),
        request_id VARCHAR(100),
        session_id VARCHAR(100),
        geo_country VARCHAR(100),
        geo_city VARCHAR(100),
        entry_metadata JSON NOT NULL,
        timestamp DATETIME NOT NULL,
        is_sensitive BOOLEAN NOT NULL,
        retention_days INTEGER NOT NULL
    )
    """,
)


class _FreshSession:
    """A session on a brand-new engine, per call.

    ``main()`` calls ``asyncio.run``, so the CLI tests execute on an event loop that
    did not exist when the fixture was built, and an engine bound to another loop
    cannot be reused across that boundary.
    """

    def __init__(self, url: str):
        self._url = url

    async def __aenter__(self) -> AsyncSession:
        self._engine = create_async_engine(self._url, poolclass=NullPool)
        self._session = AsyncSession(self._engine, expire_on_commit=False)
        return self._session

    async def __aexit__(self, *_exc: Any) -> bool:
        await self._session.close()
        await self._engine.dispose()
        return False


class _TwinsDb:
    """Production's shape: three identical audits, two of them re-imports."""

    def __init__(self, path: Any):
        self.url = f"sqlite+aiosqlite:///{path}"
        self._engine = create_engine(f"sqlite:///{path}")
        with self._engine.begin() as conn:
            for statement in _SCHEMA:
                conn.execute(text(statement))

    def seed(self, *, top_suffix: int = DEFAULT_TOP_SUFFIX) -> None:
        twin_identity = {
            "title": TWIN_TITLE,
            "auditor": TWIN_AUDITOR,
            "score": TWIN_SCORE,
        }
        with self._engine.begin() as conn:
            conn.execute(text("INSERT INTO tenants (id, name) VALUES (1, 'Plantexpand Limited'), (2, 'Other Co')"))
            conn.execute(
                text(
                    "INSERT INTO users (id, email, tenant_id) VALUES "
                    "(5, 'david.harris@plantexpand.com', 1), (6, 'other@example.com', 2)"
                )
            )
            conn.execute(text("INSERT INTO audit_templates (id, name, tenant_id) VALUES (1, 'B2 Audit', 1)"))
            conn.execute(text("INSERT INTO evidence_assets (id, tenant_id) VALUES (900, 1), (901, 1)"))
            conn.execute(text("INSERT INTO job_cells (id, tenant_id) VALUES (70, 1)"))
            conn.execute(text("INSERT INTO audit_questions (id, question_text, tenant_id) VALUES (1, 'Ok?', 1)"))

            # Every audit for the year, so the AUD reference arithmetic reflects a
            # populated register rather than three rows in isolation.
            for suffix in range(1, top_suffix + 1):
                is_twin_group = suffix in (SURVIVOR_ID, *TWIN_IDS)
                conn.execute(
                    text(
                        "INSERT INTO audit_runs (id, reference_number, template_id, title, status, "
                        "source_origin, external_auditor_name, score_percentage, completed_at, "
                        "created_at, tenant_id) VALUES (:id, :ref, 1, :title, 'completed', "
                        "'third_party', :auditor, :score, :completed, :created, 1)"
                    ),
                    {
                        "id": suffix,
                        "ref": f"AUD-2026-{suffix:04d}",
                        "title": twin_identity["title"] if is_twin_group else f"Routine inspection {suffix}",
                        "auditor": twin_identity["auditor"] if is_twin_group else f"Auditor {suffix}",
                        "score": twin_identity["score"] if is_twin_group else 80.0 + suffix,
                        # The survivor was completed first and updated later; the twins
                        # are the re-imports. Volatile columns differ, which is exactly
                        # why they are context rather than identity.
                        "completed": "2026-02-20 09:00:00",
                        "created": {
                            SURVIVOR_ID: "2026-02-21 08:00:00",
                            43: "2026-05-02 11:15:00",
                            48: "2026-06-14 16:40:00",
                        }.get(suffix, "2026-01-05 08:00:00"),
                    },
                )

            # Findings across the register, two of them on the twins.
            twin_findings = {43: 10, 48: 11}
            for suffix in range(1, 21):
                run_id = next((run for run, fnd in twin_findings.items() if fnd == suffix), SURVIVOR_ID)
                conn.execute(
                    text(
                        "INSERT INTO audit_findings (id, run_id, reference_number, title, description, "
                        "severity, finding_type, status, tenant_id) "
                        "VALUES (:id, :run, :ref, :title, 'd', 'minor', 'nonconformity', 'open', 1)"
                    ),
                    {
                        "id": suffix,
                        "run": run_id,
                        "ref": f"FND-2026-{suffix:04d}",
                        "title": f"Finding {suffix}",
                    },
                )

            for response_id, run_id in ((1, SURVIVOR_ID), (2, 43), (3, 43), (4, 48)):
                conn.execute(
                    text(
                        "INSERT INTO audit_responses (id, run_id, question_id, response_value, notes, tenant_id) "
                        "VALUES (:id, :run, 1, 'yes', 'answer', 1)"
                    ),
                    {"id": response_id, "run": run_id},
                )

            # Import lineage for the two re-imports: job -> drafts, plus the
            # external_audit_records row hanging off both the run and the job.
            for job_id, run_id, asset_id in ((5, 43, 900), (6, 48, 901)):
                conn.execute(
                    text(
                        "INSERT INTO external_audit_import_jobs (id, audit_run_id, source_document_asset_id, "
                        "tenant_id, reference_number, status, source_checksum_sha256, idempotency_key) "
                        "VALUES (:id, :run, :asset, 1, :ref, 'completed', :checksum, :key)"
                    ),
                    {
                        "id": job_id,
                        "run": run_id,
                        "asset": asset_id,
                        "ref": f"AIM-2026-{job_id:04d}",
                        "checksum": f"{job_id:064d}",
                        "key": f"idem-{job_id}",
                    },
                )
                conn.execute(
                    text(
                        "INSERT INTO external_audit_import_drafts (id, import_job_id, audit_run_id, "
                        "promoted_finding_id, tenant_id, status, title, description) "
                        "VALUES (:id, :job, :run, :finding, 1, 'promoted', 'Draft', 'd')"
                    ),
                    {"id": job_id, "job": job_id, "run": run_id, "finding": twin_findings[run_id]},
                )
                conn.execute(
                    text(
                        "INSERT INTO external_audit_records (id, tenant_id, scheme, audit_run_id, import_job_id, "
                        "company_name, score_percentage, status) VALUES (:id, 1, 'achilles_uvdb', :run, :job, "
                        "'Plantexpand Limited', :score, 'completed')"
                    ),
                    {"id": job_id, "run": run_id, "job": job_id, "score": TWIN_SCORE},
                )
            # Import lineage for the survivor too, so "import derived" does not
            # accidentally become the thing that distinguishes the twins. Plus the
            # rest of the year's imports: with only the twins' two jobs seeded,
            # deleting them would free the top of the AIM sequence and the purge
            # would correctly refuse for a reason that has nothing to do with what
            # is being tested. Production has many.
            for job_id in (1, 2, 3, 4, 7, 8, 9, 10):
                conn.execute(
                    text(
                        "INSERT INTO external_audit_import_jobs (id, audit_run_id, source_document_asset_id, "
                        "tenant_id, reference_number, status, source_checksum_sha256, idempotency_key) "
                        "VALUES (:id, :run, 900, 1, :ref, 'completed', :checksum, :key)"
                    ),
                    {
                        "id": job_id,
                        "run": SURVIVOR_ID if job_id == 4 else job_id,
                        "ref": f"AIM-2026-{job_id:04d}",
                        "checksum": f"{job_id:064d}",
                        "key": f"idem-{job_id}",
                    },
                )

            # A risk escalated from one of the doomed findings. The junction goes; the
            # risk survives and is reported as collateral.
            conn.execute(
                text(
                    "INSERT INTO risks_v2 (id, reference, title, category, description, status, "
                    "created_at, tenant_id) VALUES (2, 'RSK-2026-0002', "
                    "'Audit escalation: AUD-2026-0043 / FND-2026-0010', 'operational', 'd', 'open', "
                    "'2026-05-02 11:20:00', 1)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO audit_finding_risks (id, audit_finding_id, risk_id, created_at) "
                    "VALUES (1, 10, 2, '2026-05-02 11:20:00')"
                )
            )

            # A job cell link whose audit_run_id will be nulled by the delete.
            conn.execute(
                text(
                    "INSERT INTO job_cell_links (id, tenant_id, cell_id, kind, label, audit_run_id, sort_order) "
                    "VALUES (1, 1, 70, 'audit_outcome', 'B2 outcome', 43, 0)"
                )
            )

            # In-app notification about a doomed finding: purged, so the UI stops
            # offering a link to a record that is gone.
            conn.execute(
                text(
                    "INSERT INTO notifications (id, tenant_id, user_id, title, message, entity_type, entity_id) "
                    "VALUES (1, 1, 5, 'Finding raised', 'FND-2026-0010', 'audit_finding', '10')"
                )
            )
            # A notification about a finding that survives, to prove the delete is
            # scoped to the purge set rather than to the entity type.
            conn.execute(
                text(
                    "INSERT INTO notifications (id, tenant_id, user_id, title, message, entity_type, entity_id) "
                    "VALUES (2, 1, 5, 'Finding raised', 'FND-2026-0001', 'audit_finding', '1')"
                )
            )

            # Two existing trail entries, so the appended one has a real tail to chain
            # onto rather than starting at genesis.
            for sequence in (1, 2):
                conn.execute(
                    text(
                        "INSERT INTO audit_log_entries (id, tenant_id, sequence, entry_hash, previous_hash, "
                        "entity_type, entity_id, action, action_category, entry_metadata, timestamp, "
                        "is_sensitive, retention_days) VALUES (:id, 1, :seq, :hash, :prev, 'audit_finding', "
                        "'10', 'create', 'data', '{}', '2026-05-02 11:15:00', 0, 2555)"
                    ),
                    {
                        "id": sequence,
                        "seq": sequence,
                        "hash": f"{sequence:064d}",
                        "prev": f"{sequence - 1:064d}" if sequence > 1 else "0" * 64,
                    },
                )

    def execute(self, statement: str, **params: Any) -> None:
        with self._engine.begin() as conn:
            conn.execute(text(statement), params)

    def count(self, table: str, where: str = "1=1") -> int:
        with self._engine.begin() as conn:
            return int(conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}")).scalar() or 0)  # noqa: S608

    def scalars(self, statement: str) -> list[Any]:
        with self._engine.begin() as conn:
            return list(conn.execute(text(statement)).scalars().all())

    def rows(self, statement: str) -> list[dict[str, Any]]:
        with self._engine.begin() as conn:
            return [dict(row) for row in conn.execute(text(statement)).mappings().all()]

    def dispose(self) -> None:
        self._engine.dispose()

    def seed_finding_twins_for_remediation(self) -> None:
        """Make doomed findings 10 and 11 match survivor findings 1 and 2 by content.

        Default seed titles are unique per id, so remapping would find nothing.
        Opt-in only — existing tests assert finding counts and titles.
        """
        with self._engine.begin() as conn:
            for doomed_id, survivor_id in ((10, 1), (11, 2)):
                survivor = (
                    conn.execute(
                        text("SELECT title, description, severity, finding_type FROM audit_findings " "WHERE id = :id"),
                        {"id": survivor_id},
                    )
                    .mappings()
                    .one()
                )
                conn.execute(
                    text(
                        "UPDATE audit_findings SET title = :title, description = :description, "
                        "severity = :severity, finding_type = :finding_type WHERE id = :id"
                    ),
                    {
                        "id": doomed_id,
                        "title": survivor["title"],
                        "description": survivor["description"],
                        "severity": survivor["severity"],
                        "finding_type": survivor["finding_type"],
                    },
                )

    def seed_evidence_link(
        self,
        *,
        link_id: int,
        entity_type: str,
        entity_id: str,
        clause_id: str,
        cover_kind: str = "evidences",
        deleted_at: Optional[str] = None,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO compliance_evidence_links "
                    "(id, tenant_id, entity_type, entity_id, clause_id, cover_kind, "
                    "signal_type, linked_by, deleted_at, created_at, updated_at) "
                    "VALUES (:id, 1, :etype, :eid, :clause, :cover, 'evidence', 'auto', "
                    ":deleted, '2026-05-01 00:00:00', '2026-05-01 00:00:00')"
                ),
                {
                    "id": link_id,
                    "etype": entity_type,
                    "eid": entity_id,
                    "clause": clause_id,
                    "cover": cover_kind,
                    "deleted": deleted_at,
                },
            )


def _wire(db: _TwinsDb, monkeypatch) -> None:
    async def _open_session():
        return _FreshSession(db.url)

    for module in (purge, scanner):
        monkeypatch.setattr(module, "open_session", _open_session)
    monkeypatch.setenv("DATABASE_URL", db.url)
    for marker in ("APP_ENV", "ENVIRONMENT", "QGP_ENV"):
        monkeypatch.delenv(marker, raising=False)


@pytest.fixture
def twins_db(tmp_path, monkeypatch):
    db = _TwinsDb(tmp_path / "twins.db")
    db.seed()
    _wire(db, monkeypatch)
    try:
        yield db
    finally:
        db.dispose()


@pytest.fixture
def hazard_db(tmp_path, monkeypatch):
    """The twins at the top of the reference sequence, so deleting them frees numbers."""
    db = _TwinsDb(tmp_path / "hazard.db")
    db.seed(top_suffix=max(TWIN_IDS))
    _wire(db, monkeypatch)
    try:
        yield db
    finally:
        db.dispose()


def _dry_run_args(*extra: str) -> list[str]:
    return [
        "--tenant-id",
        str(FR_DEDUP_01_TENANT),
        *[argument for reference in FR_DEDUP_01_REFERENCES for argument in ("--reference", reference)],
        *extra,
    ]


# --------------------------------------------------------------------------- #
# The authorised set. Pinned, because it is the whole authority for a delete.
# --------------------------------------------------------------------------- #


def test_the_authorised_references_are_exactly_the_two_re_imports():
    """If a third reference is ever added here that is a new approval, and this test
    is the thing that should say so."""
    assert FR_DEDUP_01_REFERENCES == ("AUD-2026-0043", "AUD-2026-0048")
    assert SURVIVOR_REFERENCE not in FR_DEDUP_01_REFERENCES


def test_every_disposition_carries_a_rationale():
    """The rationale is copied into the manifest and is what an auditor reads. An
    entry without one is a decision nobody has to justify."""
    for rule in (*AUDIT_RUN_CHILD_DISPOSITIONS.values(), *SOFT_LINK_DISPOSITIONS.values()):
        assert rule.rationale.strip(), rule.table
        assert len(rule.rationale) > 40, f"{rule.table} rationale is too thin to be a justification"


def test_the_audit_trail_is_never_classified_purge():
    """Deleting chained entries breaks verification for everything written after
    them, and destroys the evidence that the purge itself happened."""
    assert SOFT_LINK_DISPOSITIONS["audit_log_entries"].disposition is Disposition.RETAIN


def test_the_scanner_cannot_delete_anything():
    """There is no --apply to leave off by accident, and no code path to one."""
    assert not hasattr(scanner, "apply_plan")
    with pytest.raises(SystemExit):
        scanner.main(["--apply"])


# --------------------------------------------------------------------------- #
# The child inventory: found by reflection, transitively, not by a hardcoded list.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_the_fixture_really_reflects_the_ondelete_rules_it_claims_to(twins_db):
    """A guard on the fixture itself, not on the product.

    SQLAlchemy's SQLite reflection parses ``ON DELETE`` only from table-level
    ``FOREIGN KEY`` constraints — an inline ``column REFERENCES parent(id) ON DELETE
    SET NULL`` reflects as ``NO ACTION`` with the clause silently dropped. The first
    version of this schema was written inline, so every rule below came back
    ``NO ACTION`` and the tests that depend on the difference between CASCADE, SET
    NULL and NO ACTION were all quietly passing for the wrong reason.

    PostgreSQL reads these from the catalogue and is unaffected. This test exists so
    that if the DDL is ever rewritten inline again, the failure names the cause
    instead of surfacing as a puzzling refusal somewhere else.
    """
    from scripts.ops.run025._dependencies import inbound_refs

    async with _FreshSession(twins_db.url) as db:
        refs = await db.run_sync(inbound_refs, ["audit_runs", "audit_findings"])

    actual = {
        (ref.child_table, ref.child_column): ref.on_delete for parent_refs in refs.values() for ref in parent_refs
    }
    assert actual == {
        ("audit_responses", "run_id"): "CASCADE",
        ("audit_findings", "run_id"): "CASCADE",
        ("audit_finding_risks", "audit_finding_id"): "CASCADE",
        ("external_audit_import_jobs", "audit_run_id"): "CASCADE",
        ("external_audit_import_drafts", "audit_run_id"): "CASCADE",
        ("external_audit_import_drafts", "promoted_finding_id"): "NO ACTION",
        # The two that make an explicit, ordered delete mandatory.
        ("external_audit_records", "audit_run_id"): "NO ACTION",
        ("job_cell_links", "audit_run_id"): "SET NULL",
        ("job_cell_links", "audit_finding_id"): "SET NULL",
    }


@pytest.mark.anyio
async def test_the_closure_reaches_a_grandchild_nobody_listed(twins_db):
    """``external_audit_records`` hangs off the import job, not off the audit run.

    A one-level child sweep would leave it, and because its foreign key is
    NO ACTION the delete would then fail rather than merely leave debris.
    """
    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=500)

    assert result["blockers"] == []
    assert result["rows_per_table"] == {
        "audit_findings": 2,
        "audit_finding_risks": 1,
        "audit_responses": 3,
        "audit_runs": 2,
        "external_audit_import_drafts": 2,
        "external_audit_import_jobs": 2,
        "external_audit_records": 2,
    }


@pytest.mark.anyio
async def test_the_no_action_reference_is_deleted_explicitly_before_its_parents(twins_db):
    """The ordering is what makes the purge work at all on an imported audit.

    ``external_audit_records`` must be gone before both the import job and the audit
    run it points at, and no cascade will do that.
    """
    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=500)
    order = result["deletion_order"]

    position = {row: index for index, row in enumerate(order)}
    for record_id, job_id, run_id in ((5, 5, 43), (6, 6, 48)):
        assert position[f"external_audit_records#{record_id}"] < position[f"external_audit_import_jobs#{job_id}"]
        assert position[f"external_audit_records#{record_id}"] < position[f"audit_runs#{run_id}"]

    # And every audit run is last: nothing may be deleted after its parent.
    assert {order[-1], order[-2]} == {"audit_runs#43", "audit_runs#48"}


@pytest.mark.anyio
async def test_the_junction_goes_but_the_escalated_risk_is_reported_not_deleted(twins_db):
    """Unlinking a risk is this script's business; deleting one is not."""
    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=500)

    assert ("audit_finding_risks", 1) in {
        (row["child"].split("#")[0], int(row["child"].split("#")[1])) for row in result["child_inventory"]
    }
    assert result["collateral_risks"] == [
        {
            "risk": "risks_v2#2",
            "reference": "RSK-2026-0002",
            "title": "Audit escalation: AUD-2026-0043 / FND-2026-0010",
            "was_linked_to": "audit_findings#10",
            "effect": "link removed; the risk row survives and is not touched by this purge",
        }
    ]
    assert not any(row.startswith("risks_v2#") for row in result["deletion_order"])


@pytest.mark.anyio
async def test_a_set_null_on_a_surviving_row_is_reported_rather_than_assumed_harmless(twins_db):
    """``job_cell_links`` survives, but the delete silently rewrites it. Row counts do
    not move, so this is the only place an operator would ever see it."""
    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=500)

    assert result["rows_set_to_null_outside_purge"] == [
        {
            "row": "job_cell_links#1",
            "column_set_to_null": "job_cell_links.audit_run_id",
            "was_pointing_at": "audit_runs#43",
            "rationale": AUDIT_RUN_CHILD_DISPOSITIONS["job_cell_links"].rationale,
        }
    ]


@pytest.mark.anyio
async def test_a_new_referencing_table_stops_the_purge_until_somebody_classifies_it(twins_db):
    """The shape of a future release adding a table that references audits.

    Sweeping it would destroy records nobody reviewed; ignoring it would leave
    dangling references. Neither is an acceptable default, so this refuses.
    """
    twins_db.execute(
        "CREATE TABLE audit_signoffs (id INTEGER PRIMARY KEY, "
        "run_id INTEGER REFERENCES audit_runs(id) ON DELETE CASCADE, signed_by VARCHAR(200))"
    )
    twins_db.execute("INSERT INTO audit_signoffs (id, run_id, signed_by) VALUES (1, 43, 'K Game')")

    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=500)

    assert any("audit_signoffs" in blocker and "no reviewed disposition" in blocker for blocker in result["blockers"])


# --------------------------------------------------------------------------- #
# Soft references: the links reflection cannot see.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_a_capa_raised_from_a_doomed_finding_stops_the_purge(twins_db):
    """No foreign key holds this, so the delete would neither cascade nor fail — it
    would leave a governed corrective action pointing at nothing."""
    twins_db.execute(
        "INSERT INTO capa_actions (id, tenant_id, reference_number, title, capa_type, status, "
        "source_type, source_id) VALUES (1, 1, 'CAPA-2026-0007', 'Fix the gate', 'corrective', "
        "'open', 'audit_finding', 10)"
    )

    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=500)

    assert any("capa_actions" in blocker and "must-not-touch" in blocker for blocker in result["blockers"])
    assert any(
        entry["table"] == "capa_actions" and entry["disposition"] == "refuse" for entry in result["soft_references"]
    )


@pytest.mark.anyio
async def test_a_notification_about_a_doomed_finding_is_purged_but_one_about_a_survivor_is_not(twins_db):
    """Scoped to the purge set, not to the entity type."""
    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=500)

    hits = [entry for entry in result["soft_references"] if entry["table"] == "notifications"]
    assert len(hits) == 1
    assert hits[0]["disposition"] == "purge"
    assert hits[0]["row_ids"] == [1]


@pytest.mark.anyio
async def test_the_trail_entries_about_the_purged_finding_are_retained(twins_db):
    """Reported, deliberately, as surviving their subject."""
    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=500)

    hits = [entry for entry in result["soft_references"] if entry["table"] == "audit_log_entries"]
    assert hits and all(entry["disposition"] == "retain" for entry in hits)


# --------------------------------------------------------------------------- #
# Refusals that protect the register.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_a_mistyped_reference_refuses_instead_of_reporting_all_clear(twins_db):
    result = await plan(references=["AUD-2026-0043", "AUD-2026-0480"], tenant_id=1, limit=50)

    assert any("AUD-2026-0480 does not exist" in blocker for blocker in result["blockers"])
    assert result["deletion_order"] == []


@pytest.mark.anyio
async def test_a_reference_belonging_to_another_tenant_refuses(twins_db):
    """A globally-unique reference resolves perfectly to the wrong record when the
    operator is pointed at the wrong tenant's data."""
    twins_db.execute("UPDATE audit_runs SET tenant_id = 2 WHERE reference_number = 'AUD-2026-0048'")

    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=50)

    assert any("belongs to tenant 2" in blocker for blocker in result["blockers"])


@pytest.mark.anyio
async def test_purging_the_whole_duplicate_group_refuses(twins_db):
    """With the survivor gone, removing the twins is not deduplication — it is
    destroying the only remaining copy of an audit."""
    twins_db.execute("UPDATE audit_runs SET title = 'Something else' WHERE id = :id", id=SURVIVOR_ID)

    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=50)

    assert result["_survivor_blockers"]
    assert all("would leave nothing sharing its identity" in blocker for blocker in result["_survivor_blockers"])


@pytest.mark.anyio
async def test_the_survivor_is_named_so_an_operator_can_check_it(twins_db):
    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=50)

    for entry in result["duplicate_group_survivors"]:
        assert entry["group_size"] == 3
        assert [survivor["reference"] for survivor in entry["survivors"]] == [SURVIVOR_REFERENCE]


def test_purging_the_whole_group_is_refused_at_the_cli_and_overridable(twins_db):
    twins_db.execute("UPDATE audit_runs SET title = 'Something else' WHERE id = :id", id=SURVIVOR_ID)

    assert purge_main(_dry_run_args("--json")) == 3
    # Overridden, it drops back to an ordinary dry run rather than deleting.
    assert purge_main(_dry_run_args("--json", "--allow-no-survivor")) == 1
    assert twins_db.count("audit_runs") == DEFAULT_TOP_SUFFIX


def test_freeing_the_top_of_the_reference_sequence_is_refused_and_overridable(hazard_db):
    """``AUD-2026-0048`` is the highest audit reference, so deleting it lowers the
    next value the application will mint and a future audit reuses the number."""
    assert purge_main(_dry_run_args("--json")) == 3
    assert purge_main(_dry_run_args("--json", "--accept-reference-reuse-risk")) == 1
    assert hazard_db.count("audit_runs") == max(TWIN_IDS)


@pytest.mark.anyio
async def test_the_reference_check_covers_child_tables_not_just_the_audit_register(twins_db):
    """The findings and import jobs being deleted mint their own references.

    A collision on ``FND`` stops anyone raising a finding at all, so the arithmetic is
    run for every purged table that has a reference column — not only ``audit_runs``.
    Here the twins' import jobs are made the highest in the ``AIM`` sequence.
    """
    twins_db.execute("DELETE FROM external_audit_import_jobs WHERE id IN (7, 8, 9, 10)")

    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=500)

    hazardous = {entry["table"] for entry in result["_hazards"]}
    assert hazardous == {"external_audit_import_jobs"}
    assert {entry["table"] for entry in result["reference_arithmetic"]} == {
        "audit_runs",
        "audit_findings",
        "external_audit_import_jobs",
    }


def test_a_populated_register_is_not_in_reference_danger(twins_db):
    """The same purge against production's real reference spread is safe, which is
    why the hazard check is a check and not a blanket refusal."""
    assert purge_main(_dry_run_args("--json")) == 1


# --------------------------------------------------------------------------- #
# Dry-run default and the apply gates.
# --------------------------------------------------------------------------- #


def test_dry_run_is_the_default_and_writes_nothing(twins_db, capsys):
    before = {table: twins_db.count(table) for table in ("audit_runs", "audit_findings", "external_audit_records")}

    assert purge_main(_dry_run_args("--json")) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "dry-run"
    assert payload["rows_to_delete"] == 14
    assert {table: twins_db.count(table) for table in before} == before


def test_apply_without_a_manifest_is_refused(twins_db):
    assert purge_main(_dry_run_args("--json", "--apply")) == 2
    assert twins_db.count("audit_runs") == DEFAULT_TOP_SUFFIX


def test_apply_on_a_production_like_environment_without_the_acknowledgement_aborts(twins_db, monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(SystemExit) as excinfo:
        purge_main(_dry_run_args("--apply", "--manifest", str(tmp_path / "m.json")))

    assert excinfo.value.code == 2
    assert twins_db.count("audit_runs") == DEFAULT_TOP_SUFFIX


def test_apply_without_an_asserted_tenant_is_refused(twins_db, tmp_path):
    arguments = [
        *[argument for reference in FR_DEDUP_01_REFERENCES for argument in ("--reference", reference)],
        "--apply",
        "--manifest",
        str(tmp_path / "m.json"),
        "--json",
    ]
    assert purge_main(arguments) == 3
    assert twins_db.count("audit_runs") == DEFAULT_TOP_SUFFIX


def test_no_reference_deletes_nothing(twins_db):
    assert purge_main(["--tenant-id", "1", "--json"]) == 3
    assert twins_db.count("audit_runs") == DEFAULT_TOP_SUFFIX


# --------------------------------------------------------------------------- #
# The purge itself.
# --------------------------------------------------------------------------- #


def test_apply_removes_the_twins_and_their_children_and_leaves_the_survivor(twins_db, tmp_path, capsys):
    manifest = tmp_path / "manifest.json"

    assert purge_main(_dry_run_args("--json", "--apply", "--manifest", str(manifest))) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "applied"

    # The twins are gone, as if never imported.
    assert twins_db.scalars("SELECT reference_number FROM audit_runs WHERE id IN (43, 48)") == []
    assert twins_db.count("audit_responses", "run_id IN (43, 48)") == 0
    assert twins_db.count("audit_findings", "run_id IN (43, 48)") == 0
    assert twins_db.count("external_audit_import_jobs", "audit_run_id IN (43, 48)") == 0
    assert twins_db.count("external_audit_import_drafts", "audit_run_id IN (43, 48)") == 0
    assert twins_db.count("external_audit_records", "audit_run_id IN (43, 48)") == 0
    assert twins_db.count("audit_finding_risks") == 0

    # The survivor and the rest of the register are untouched.
    assert twins_db.count("audit_runs") == DEFAULT_TOP_SUFFIX - 2
    assert SURVIVOR_REFERENCE in twins_db.scalars("SELECT reference_number FROM audit_runs")
    assert twins_db.count("audit_findings") == 18
    assert twins_db.count("audit_responses", "run_id = 31") == 1
    # The escalated risk survives; only its link went.
    assert twins_db.count("risks_v2", "id = 2") == 1

    manifest_payload = json.loads(manifest.read_text())
    assert [row["reference_number"] for row in manifest_payload["rows"]["audit_runs"]] == list(FR_DEDUP_01_REFERENCES)
    assert manifest_payload["requirement"] == "FR-DEDUP-01"


def test_apply_purges_the_notification_and_keeps_the_one_about_a_surviving_finding(twins_db, tmp_path):
    assert purge_main(_dry_run_args("--json", "--apply", "--manifest", str(tmp_path / "m.json"))) == 0

    assert twins_db.scalars("SELECT id FROM notifications ORDER BY id") == [2]


def test_apply_nulls_the_job_cell_link_without_destroying_the_job_data(twins_db, tmp_path):
    """SQLite does not enforce foreign keys by default, so the SET NULL is applied
    explicitly here to assert the *intended* production behaviour: the link clears
    and the row survives. What the dry run promised is that the row is not deleted,
    and that is what is checked."""
    assert purge_main(_dry_run_args("--json", "--apply", "--manifest", str(tmp_path / "m.json"))) == 0

    assert twins_db.count("job_cell_links", "id = 1") == 1


def test_apply_appends_one_chained_trail_entry_describing_the_purge(twins_db, tmp_path):
    tail_before = twins_db.rows("SELECT sequence, entry_hash FROM audit_log_entries ORDER BY sequence DESC LIMIT 1")[0]

    assert purge_main(_dry_run_args("--json", "--apply", "--manifest", str(tmp_path / "m.json"))) == 0

    entries = twins_db.rows("SELECT * FROM audit_log_entries ORDER BY sequence")
    # The two seeded entries about the purged finding are retained, not tidied away.
    assert [entry["sequence"] for entry in entries] == [1, 2, 3]

    appended = entries[-1]
    assert appended["sequence"] == tail_before["sequence"] + 1
    assert appended["previous_hash"] == tail_before["entry_hash"]
    assert appended["action"] == "delete"
    assert appended["entity_type"] == "audit_run"
    assert appended["entity_id"] == ",".join(FR_DEDUP_01_REFERENCES)
    assert json.loads(appended["entry_metadata"])["requirement"] == "FR-DEDUP-01"
    # The entry records what was destroyed, not merely that something was.
    assert [row["reference_number"] for row in json.loads(appended["old_values"])["audit_runs"]] == list(
        FR_DEDUP_01_REFERENCES
    )


def test_the_trail_entry_hash_matches_the_models_own_computation(twins_db, tmp_path):
    """Recomputed with ``AuditLogEntry.compute_hash`` rather than compared to a
    literal, so the chain stays verifiable if the hash definition ever changes."""
    from src.domain.models.audit_log import AuditLogEntry

    assert purge_main(_dry_run_args("--json", "--apply", "--manifest", str(tmp_path / "m.json"))) == 0

    entry = twins_db.rows("SELECT * FROM audit_log_entries ORDER BY sequence DESC LIMIT 1")[0]
    from datetime import datetime

    recomputed = AuditLogEntry.compute_hash(
        sequence=entry["sequence"],
        previous_hash=entry["previous_hash"],
        entity_type=entry["entity_type"],
        entity_id=entry["entity_id"],
        action=entry["action"],
        user_id=entry["user_id"],
        timestamp=datetime.fromisoformat(str(entry["timestamp"])),
        old_values=json.loads(entry["old_values"]),
        new_values=json.loads(entry["new_values"]),
    )
    assert entry["entry_hash"] == recomputed


def test_a_second_apply_refuses_because_the_references_are_gone(twins_db, tmp_path):
    """The purge is not idempotent by design: a reference that is already gone is
    indistinguishable from one that was mistyped."""
    assert purge_main(_dry_run_args("--json", "--apply", "--manifest", str(tmp_path / "m1.json"))) == 0
    assert purge_main(_dry_run_args("--json", "--apply", "--manifest", str(tmp_path / "m2.json"))) == 3


def test_nothing_is_deleted_when_the_trail_cannot_be_written(twins_db, tmp_path, monkeypatch):
    """The deletes and the trail entry share one transaction. If the register cannot
    record what happened, it must not happen."""

    async def _explode(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("chain unavailable")

    monkeypatch.setattr(purge, "record_purge", _explode)

    with pytest.raises(RuntimeError, match="chain unavailable"):
        purge_main(_dry_run_args("--json", "--apply", "--manifest", str(tmp_path / "m.json")))

    assert twins_db.count("audit_runs") == DEFAULT_TOP_SUFFIX
    assert twins_db.count("external_audit_records") == 2
    assert twins_db.scalars("SELECT id FROM notifications ORDER BY id") == [1, 2]


# --------------------------------------------------------------------------- #
# The broader scan.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_the_scanner_finds_the_group_of_three_and_marks_it_import_derived(twins_db):
    result = await scanner.scan(tenant_id=1, limit=50, min_group_size=2)

    audit_groups = [group for group in result["groups"] if group["table"] == "audit_runs"]
    assert len(audit_groups) == 1
    group = audit_groups[0]
    assert group["count"] == 3
    assert sorted(member["id"] for member in group["members"]) == [SURVIVOR_ID, *TWIN_IDS]
    assert group["import_derived"] == 3
    assert group["identity"]["title"] == TWIN_TITLE.casefold()
    # created_at is reported so a human can tell the original from the re-imports.
    assert all(member["created_at"] for member in group["members"])


@pytest.mark.anyio
async def test_the_scanner_reports_registers_it_did_not_examine(twins_db):
    """ "No duplicates found" and "not looked at" are different answers."""
    result = await scanner.scan(tenant_id=1, limit=50, min_group_size=2)

    skipped = {entry["register"] for entry in result["registers_skipped"]}
    # The fixture has no incident/complaint/RTA registers at all.
    assert "cases_incidents" in skipped
    assert all(entry["reason"] for entry in result["registers_skipped"])


@pytest.mark.anyio
async def test_the_scanner_ignores_a_register_it_could_only_group_on_a_title(tmp_path, monkeypatch):
    """Grouping on one free-text column would report every "Site inspection" as a
    duplicate of every other, and somebody eventually approves a delete from that."""
    db = _TwinsDb(tmp_path / "thin.db")
    db.seed()
    db.execute("CREATE TABLE incidents (id INTEGER PRIMARY KEY, title VARCHAR(300), tenant_id INTEGER)")
    _wire(db, monkeypatch)
    try:
        result = await scanner.scan(tenant_id=1, limit=50, min_group_size=2)
        reasons = {entry["register"]: entry["reason"] for entry in result["registers_skipped"]}
        assert "cases_incidents" in reasons
        assert "identity columns exist" in reasons["cases_incidents"]
    finally:
        db.dispose()


def test_rows_whose_identity_is_entirely_null_are_not_reported_as_duplicates():
    """Blank drafts group with one another for no reason but being blank, and
    reporting them buries the rows that matter.

    Exercised directly against ``group_duplicates`` rather than through a seeded
    database: ``audit_runs.template_id`` is NOT NULL, so a row with a wholly null
    identity cannot be inserted there at all. The registers where it can — a draft
    complaint with nothing filled in — are not part of this fixture's schema.
    """
    from scripts.ops.run027._duplicates import ResolvedRegister, group_duplicates

    register = ResolvedRegister(
        spec=next(spec for spec in REGISTERS if spec.table == "audit_runs"),
        table="audit_runs",
        key_column="id",
        reference_column="reference_number",
        identity_columns=("title", "status"),
        context_columns=(),
        has_tenant=True,
    )
    rows = [
        {"id": 101, "tenant_id": 1, "title": None, "status": None},
        {"id": 102, "tenant_id": 1, "title": None, "status": None},
        {"id": 103, "tenant_id": 1, "title": "Yard sweep", "status": "completed"},
        {"id": 104, "tenant_id": 1, "title": "Yard sweep", "status": "completed"},
    ]

    groups = group_duplicates(rows, register)

    assert len(groups) == 1
    assert sorted(member["id"] for member in groups[0]["members"]) == [103, 104]


@pytest.mark.anyio
async def test_casing_and_padding_do_not_split_a_group_but_punctuation_does(twins_db):
    """Normalisation is deliberately shallow.

    Collapsing punctuation would merge "Gate 3 check" with "Gate 3 - check", which
    are plausibly different audits, and this report feeds a delete review.
    """
    from scripts.ops.run027._duplicates import ResolvedRegister, group_duplicates

    register = ResolvedRegister(
        spec=next(spec for spec in REGISTERS if spec.table == "audit_runs"),
        table="audit_runs",
        key_column="id",
        reference_column=None,
        identity_columns=("title", "status"),
        context_columns=(),
        has_tenant=True,
    )
    rows = [
        {"id": 1, "tenant_id": 1, "title": "Gate 3 check", "status": "completed"},
        {"id": 2, "tenant_id": 1, "title": "  GATE 3   CHECK ", "status": "completed"},
        {"id": 3, "tenant_id": 1, "title": "Gate 3 - check", "status": "completed"},
    ]

    groups = group_duplicates(rows, register)

    assert len(groups) == 1
    assert sorted(member["id"] for member in groups[0]["members"]) == [1, 2]


@pytest.mark.anyio
async def test_the_scan_is_tenant_scoped(twins_db):
    twins_db.execute("UPDATE audit_runs SET tenant_id = 2 WHERE id = :id", id=48)

    result = await scanner.scan(tenant_id=1, limit=50, min_group_size=2)

    audit_groups = [group for group in result["groups"] if group["table"] == "audit_runs"]
    assert [group["count"] for group in audit_groups] == [2]
    assert 48 not in {member["id"] for group in audit_groups for member in group["members"]}


def test_every_register_declares_enough_identity_columns_to_be_meaningful():
    """A spec that could never reach the minimum would silently never be scanned."""
    for spec in REGISTERS:
        assert len(spec.identity_candidates) >= MIN_IDENTITY_COLUMNS, spec.name


@pytest.mark.anyio
async def test_a_child_whose_primary_key_is_not_called_id_is_still_addressable(twins_db):
    """Every table in this schema happens to call its key ``id``, and relying on that
    would delete by a column the row was never selected by.

    The closure records the reflected key per table so the snapshot and the delete use
    it. Without that this row would be found and then deleted with ``WHERE id = ...``,
    which raises ``UndefinedColumn`` on PostgreSQL mid-purge.
    """
    from scripts.ops.run027._closure import ChildDisposition, row_snapshots

    twins_db.execute(
        "CREATE TABLE audit_attachments (attachment_pk INTEGER PRIMARY KEY, run_id INTEGER, note TEXT, "
        "FOREIGN KEY (run_id) REFERENCES audit_runs(id) ON DELETE CASCADE)"
    )
    twins_db.execute("INSERT INTO audit_attachments (attachment_pk, run_id, note) VALUES (77, 43, 'scan.pdf')")

    dispositions = {
        **AUDIT_RUN_CHILD_DISPOSITIONS,
        "audit_attachments": ChildDisposition(
            table="audit_attachments",
            disposition=Disposition.PURGE,
            rationale="Test-only table standing in for a child whose primary key is not named id.",
        ),
    }

    async with _FreshSession(twins_db.url) as db:
        closure = await descendant_closure(db, roots=[("audit_runs", 43)], dispositions=dispositions)
        snapshots = await row_snapshots(db, sorted(closure.purge_keys), closure.key_columns)

    assert closure.blockers == []
    assert closure.key_columns["audit_attachments"] == "attachment_pk"
    assert closure.key_columns["audit_runs"] == "id"
    assert ("audit_attachments", 77) in closure.purge_keys
    assert snapshots["audit_attachments"] == [{"attachment_pk": 77, "run_id": 43, "note": "scan.pdf"}]


@pytest.mark.anyio
async def test_the_closure_of_an_audit_with_no_children_is_just_itself(twins_db):
    """A hand-created audit with nothing hanging off it still purges cleanly."""
    twins_db.execute(
        "INSERT INTO audit_runs (id, reference_number, template_id, title, status, tenant_id) "
        "VALUES (200, 'AUD-2026-0200', 1, :title, 'draft', 1)",
        title=TWIN_TITLE,
    )
    async with _FreshSession(twins_db.url) as db:
        closure = await descendant_closure(db, roots=[("audit_runs", 200)])

    assert closure.purge_keys == {("audit_runs", 200)}
    assert closure.blockers == []
    assert closure.found == []


# --------------------------------------------------------------------------- #
# FR-DEDUP-01 follow-up: CEL remap, CAPA reassign, --survivor-reference.
# --------------------------------------------------------------------------- #


def test_audit_identity_still_includes_lifecycle_columns():
    """Lifecycle columns stay in REGISTERS so the scanner's grouping does not widen."""
    audits = next(spec for spec in REGISTERS if spec.table == "audit_runs")
    assert "status" in audits.identity_candidates
    assert "score_percentage" in audits.identity_candidates
    assert LIFECYCLE_IDENTITY_COLUMNS == frozenset({"status", "score_percentage"})


@pytest.mark.anyio
async def test_a_compliance_evidence_link_on_a_doomed_finding_stops_the_purge(twins_db):
    twins_db.seed_evidence_link(link_id=4501, entity_type="audit_finding", entity_id="10", clause_id="4.1")

    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=500)

    assert any("compliance_evidence_links" in blocker and "must-not-touch" in blocker for blocker in result["blockers"])
    assert any(
        entry["table"] == "compliance_evidence_links" and entry["disposition"] == "refuse"
        for entry in result["soft_references"]
    )


@pytest.mark.anyio
async def test_remap_evidence_without_survivor_reference_refuses(twins_db):
    twins_db.seed_finding_twins_for_remediation()
    twins_db.seed_evidence_link(link_id=4501, entity_type="audit_finding", entity_id="10", clause_id="4.1")

    result = await plan(
        references=list(FR_DEDUP_01_REFERENCES),
        tenant_id=1,
        limit=500,
        remap_evidence_links=True,
        expect_evidence_links=1,
    )

    assert any("require --survivor-reference" in blocker for blocker in result["blockers"])


@pytest.mark.anyio
async def test_remap_evidence_without_expect_count_refuses_and_states_the_count(twins_db):
    twins_db.seed_finding_twins_for_remediation()
    twins_db.seed_evidence_link(link_id=4501, entity_type="audit_finding", entity_id="10", clause_id="4.1")

    result = await plan(
        references=list(FR_DEDUP_01_REFERENCES),
        tenant_id=1,
        limit=500,
        survivor_references=[SURVIVOR_REFERENCE],
        remap_evidence_links=True,
    )

    assert any("--expect-evidence-links" in blocker for blocker in result["blockers"])
    assert any("1 actionable" in blocker or "1 soft-link" in blocker for blocker in result["blockers"])


@pytest.mark.anyio
async def test_remap_evidence_with_wrong_expect_count_refuses(twins_db):
    twins_db.seed_finding_twins_for_remediation()
    twins_db.seed_evidence_link(link_id=4501, entity_type="audit_finding", entity_id="10", clause_id="4.1")

    result = await plan(
        references=list(FR_DEDUP_01_REFERENCES),
        tenant_id=1,
        limit=500,
        survivor_references=[SURVIVOR_REFERENCE],
        remap_evidence_links=True,
        expect_evidence_links=970,
    )

    assert any("expect-evidence-links 970 but found 1" in blocker for blocker in result["blockers"])


def test_apply_remaps_evidence_link_to_matching_survivor_finding(twins_db, tmp_path, capsys):
    twins_db.seed_finding_twins_for_remediation()
    twins_db.seed_evidence_link(link_id=4501, entity_type="audit_finding", entity_id="10", clause_id="4.1")
    # Survivor already covers a different clause — must stay untouched.
    twins_db.seed_evidence_link(link_id=4600, entity_type="audit_finding", entity_id="1", clause_id="7.5")

    manifest = tmp_path / "manifest.json"
    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--apply",
                "--manifest",
                str(manifest),
                "--survivor-reference",
                SURVIVOR_REFERENCE,
                "--remap-evidence-links",
                "--expect-evidence-links",
                "1",
                "--actor-email",
                "david.harris@plantexpand.com",
            )
        )
        == 0
    )

    rows = twins_db.rows("SELECT id, entity_id, clause_id, deleted_at FROM compliance_evidence_links ORDER BY id")
    by_id = {row["id"]: row for row in rows}
    assert by_id[4501]["entity_id"] == "1"
    assert by_id[4501]["deleted_at"] is None
    assert by_id[4600]["entity_id"] == "1"
    assert by_id[4600]["clause_id"] == "7.5"
    assert twins_db.count("audit_runs", "id IN (43, 48)") == 0
    assert twins_db.count("audit_runs", f"id = {SURVIVOR_ID}") == 1


def test_apply_withdraws_redundant_evidence_when_survivor_already_covers_clause(twins_db, tmp_path):
    twins_db.seed_finding_twins_for_remediation()
    twins_db.seed_evidence_link(link_id=4501, entity_type="audit_finding", entity_id="10", clause_id="4.1")
    twins_db.seed_evidence_link(link_id=4600, entity_type="audit_finding", entity_id="1", clause_id="4.1")

    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--apply",
                "--manifest",
                str(tmp_path / "m.json"),
                "--survivor-reference",
                SURVIVOR_REFERENCE,
                "--remap-evidence-links",
                "--expect-evidence-links",
                "1",
                "--actor-email",
                "ops@example.com",
            )
        )
        == 0
    )

    rows = twins_db.rows(
        "SELECT id, entity_id, deleted_at FROM compliance_evidence_links WHERE clause_id = '4.1' ORDER BY id"
    )
    live = [row for row in rows if row["deleted_at"] is None]
    assert len(live) == 1
    assert live[0]["id"] == 4600
    withdrawn = next(row for row in rows if row["id"] == 4501)
    assert withdrawn["deleted_at"] is not None


def test_unmappable_evidence_refuses_until_withdraw_flag(twins_db, tmp_path):
    # Doomed finding 10 keeps a unique title — no survivor twin.
    twins_db.seed_evidence_link(link_id=4501, entity_type="audit_finding", entity_id="10", clause_id="4.1")

    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--survivor-reference",
                SURVIVOR_REFERENCE,
                "--remap-evidence-links",
                "--expect-evidence-links",
                "1",
            )
        )
        == 3
    )

    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--apply",
                "--manifest",
                str(tmp_path / "m.json"),
                "--survivor-reference",
                SURVIVOR_REFERENCE,
                "--remap-evidence-links",
                "--expect-evidence-links",
                "1",
                "--withdraw-unmappable-evidence",
                "--actor-email",
                "ops@example.com",
            )
        )
        == 0
    )
    row = twins_db.rows("SELECT deleted_at FROM compliance_evidence_links WHERE id = 4501")[0]
    assert row["deleted_at"] is not None


def test_already_soft_deleted_evidence_is_retained_and_not_counted(twins_db, tmp_path):
    twins_db.seed_finding_twins_for_remediation()
    twins_db.seed_evidence_link(
        link_id=4501,
        entity_type="audit_finding",
        entity_id="10",
        clause_id="4.1",
        deleted_at="2026-04-01 00:00:00",
    )
    twins_db.seed_evidence_link(link_id=4502, entity_type="audit_finding", entity_id="10", clause_id="4.2")

    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--apply",
                "--manifest",
                str(tmp_path / "m.json"),
                "--survivor-reference",
                SURVIVOR_REFERENCE,
                "--remap-evidence-links",
                "--expect-evidence-links",
                "1",
                "--actor-email",
                "ops@example.com",
            )
        )
        == 0
    )
    rows = {row["id"]: row for row in twins_db.rows("SELECT id, entity_id, deleted_at FROM compliance_evidence_links")}
    assert rows[4501]["deleted_at"] is not None
    assert rows[4501]["entity_id"] == "10"  # not remapped
    assert rows[4502]["entity_id"] == "1"
    assert rows[4502]["deleted_at"] is None


def test_audit_run_level_evidence_link_repoints_to_survivor_run(twins_db, tmp_path):
    twins_db.seed_evidence_link(link_id=4700, entity_type="audit_run", entity_id="43", clause_id="9.2")

    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--apply",
                "--manifest",
                str(tmp_path / "m.json"),
                "--survivor-reference",
                SURVIVOR_REFERENCE,
                "--remap-evidence-links",
                "--expect-evidence-links",
                "1",
                "--actor-email",
                "ops@example.com",
            )
        )
        == 0
    )
    row = twins_db.rows("SELECT entity_id, deleted_at FROM compliance_evidence_links WHERE id = 4700")[0]
    assert row["entity_id"] == str(SURVIVOR_ID)
    assert row["deleted_at"] is None


def test_capa_reassign_requires_exact_expect_ids(twins_db):
    twins_db.seed_finding_twins_for_remediation()
    twins_db.execute(
        "INSERT INTO capa_actions (id, tenant_id, reference_number, title, capa_type, status, "
        "source_type, source_id) VALUES (18, 1, 'CAPA-2026-0018', 'Fix A', 'corrective', "
        "'open', 'audit_finding', 10)"
    )
    twins_db.execute(
        "INSERT INTO capa_actions (id, tenant_id, reference_number, title, capa_type, status, "
        "source_type, source_id) VALUES (60, 1, 'CAPA-2026-0060', 'Fix B', 'corrective', "
        "'open', 'audit_finding', 11)"
    )

    # Subset refuses.
    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--survivor-reference",
                SURVIVOR_REFERENCE,
                "--reassign-capa-to-survivor",
                "--expect-capa-action",
                "18",
            )
        )
        == 3
    )
    # Superset refuses.
    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--survivor-reference",
                SURVIVOR_REFERENCE,
                "--reassign-capa-to-survivor",
                "--expect-capa-action",
                "18",
                "--expect-capa-action",
                "60",
                "--expect-capa-action",
                "99",
            )
        )
        == 3
    )


def test_apply_reassigns_capa_to_survivor_finding(twins_db, tmp_path):
    twins_db.seed_finding_twins_for_remediation()
    twins_db.execute(
        "INSERT INTO capa_actions (id, tenant_id, reference_number, title, capa_type, status, "
        "source_type, source_id) VALUES (18, 1, 'CAPA-2026-0018', 'Fix A', 'corrective', "
        "'open', 'audit_finding', 10)"
    )

    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--apply",
                "--manifest",
                str(tmp_path / "m.json"),
                "--survivor-reference",
                SURVIVOR_REFERENCE,
                "--reassign-capa-to-survivor",
                "--expect-capa-action",
                "18",
                "--actor-email",
                "ops@example.com",
            )
        )
        == 0
    )
    row = twins_db.rows("SELECT source_id, reference_number, title, status FROM capa_actions WHERE id = 18")[0]
    assert row["source_id"] == 1
    assert row["reference_number"] == "CAPA-2026-0018"
    assert row["title"] == "Fix A"
    assert row["status"] == "open"


def test_two_capas_converging_on_one_survivor_finding_refuse(twins_db):
    twins_db.seed_finding_twins_for_remediation()
    # Both doomed findings map to survivor finding 1 — make 11 also match finding 1.
    twins_db.execute(
        "UPDATE audit_findings SET title = (SELECT title FROM audit_findings WHERE id = 1), "
        "description = (SELECT description FROM audit_findings WHERE id = 1), "
        "severity = (SELECT severity FROM audit_findings WHERE id = 1), "
        "finding_type = (SELECT finding_type FROM audit_findings WHERE id = 1) WHERE id = 11"
    )
    twins_db.execute(
        "INSERT INTO capa_actions (id, tenant_id, reference_number, title, capa_type, status, "
        "source_type, source_id) VALUES (18, 1, 'CAPA-2026-0018', 'Fix A', 'corrective', "
        "'open', 'audit_finding', 10)"
    )
    twins_db.execute(
        "INSERT INTO capa_actions (id, tenant_id, reference_number, title, capa_type, status, "
        "source_type, source_id) VALUES (60, 1, 'CAPA-2026-0060', 'Fix B', 'corrective', "
        "'open', 'audit_finding', 11)"
    )

    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--survivor-reference",
                SURVIVOR_REFERENCE,
                "--reassign-capa-to-survivor",
                "--expect-capa-action",
                "18",
                "--expect-capa-action",
                "60",
            )
        )
        == 3
    )


def test_unmappable_capa_has_no_withdraw_override(twins_db):
    twins_db.execute(
        "INSERT INTO capa_actions (id, tenant_id, reference_number, title, capa_type, status, "
        "source_type, source_id) VALUES (18, 1, 'CAPA-2026-0018', 'Fix A', 'corrective', "
        "'open', 'audit_finding', 10)"
    )

    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--survivor-reference",
                SURVIVOR_REFERENCE,
                "--reassign-capa-to-survivor",
                "--expect-capa-action",
                "18",
                "--remap-evidence-links",
                "--expect-evidence-links",
                "0",
                "--withdraw-unmappable-evidence",
                "--allow-no-survivor",
            )
        )
        == 3
    )


def test_named_survivor_supersedes_identity_group_when_lifecycle_diverges(twins_db):
    """PROD shape: 0048 completed@99 while siblings are pending — identity group alone fails."""
    twins_db.execute(
        "UPDATE audit_runs SET status = 'pending_review', score_percentage = NULL " "WHERE id = :id",
        id=SURVIVOR_ID,
    )
    twins_db.execute("UPDATE audit_runs SET status = 'pending_review', score_percentage = NULL WHERE id = 43")
    twins_db.execute("UPDATE audit_runs SET status = 'completed', score_percentage = 99.0 WHERE id = 48")

    assert purge_main(_dry_run_args("--json")) == 3
    assert purge_main(_dry_run_args("--json", "--survivor-reference", SURVIVOR_REFERENCE)) == 1


def test_bad_survivor_reference_is_not_rescued_by_allow_no_survivor(twins_db):
    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--survivor-reference",
                "AUD-2026-9999",
                "--allow-no-survivor",
            )
        )
        == 3
    )
    twins_db.execute("UPDATE audit_runs SET tenant_id = 2 WHERE id = :id", id=SURVIVOR_ID)
    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--survivor-reference",
                SURVIVOR_REFERENCE,
                "--allow-no-survivor",
            )
        )
        == 3
    )


def test_without_remediation_flags_cli_still_refuses_on_cel_and_capa(twins_db):
    """Regression guard on blocker deferral: empty remediable must not drop refusals."""
    twins_db.seed_evidence_link(link_id=4501, entity_type="audit_finding", entity_id="10", clause_id="4.1")
    twins_db.execute(
        "INSERT INTO capa_actions (id, tenant_id, reference_number, title, capa_type, status, "
        "source_type, source_id) VALUES (18, 1, 'CAPA-2026-0018', 'Fix A', 'corrective', "
        "'open', 'audit_finding', 10)"
    )
    assert purge_main(_dry_run_args("--json")) == 3


@pytest.mark.anyio
async def test_without_flags_soft_refuse_blockers_still_name_both_tables(twins_db):
    twins_db.seed_evidence_link(link_id=4501, entity_type="audit_finding", entity_id="10", clause_id="4.1")
    twins_db.execute(
        "INSERT INTO capa_actions (id, tenant_id, reference_number, title, capa_type, status, "
        "source_type, source_id) VALUES (18, 1, 'CAPA-2026-0018', 'Fix A', 'corrective', "
        "'open', 'audit_finding', 10)"
    )

    result = await plan(references=list(FR_DEDUP_01_REFERENCES), tenant_id=1, limit=500)
    joined = " | ".join(result["blockers"])
    assert "compliance_evidence_links" in joined and "must-not-touch" in joined
    assert "capa_actions" in joined and "must-not-touch" in joined


def test_remediation_is_recorded_in_trail_new_values(twins_db, tmp_path):
    twins_db.seed_finding_twins_for_remediation()
    twins_db.seed_evidence_link(link_id=4501, entity_type="audit_finding", entity_id="10", clause_id="4.1")

    assert (
        purge_main(
            _dry_run_args(
                "--json",
                "--apply",
                "--manifest",
                str(tmp_path / "m.json"),
                "--survivor-reference",
                SURVIVOR_REFERENCE,
                "--remap-evidence-links",
                "--expect-evidence-links",
                "1",
                "--actor-email",
                "ops@example.com",
            )
        )
        == 0
    )
    import json as _json

    entry = twins_db.rows(
        "SELECT new_values, old_values, entry_hash, sequence, previous_hash, entity_type, "
        "entity_id, action, timestamp FROM audit_log_entries ORDER BY sequence DESC LIMIT 1"
    )[0]
    new_values = entry["new_values"]
    old_values = entry["old_values"]
    if isinstance(new_values, str):
        new_values = _json.loads(new_values)
    if isinstance(old_values, str):
        old_values = _json.loads(old_values)
    assert "remediation" in new_values
    assert new_values["remediation"]["evidence_summary"]["REMAP"] == 1

    from datetime import datetime

    from src.domain.models.audit_log import AuditLogEntry

    recomputed = AuditLogEntry.compute_hash(
        sequence=entry["sequence"],
        previous_hash=entry["previous_hash"],
        entity_type=entry["entity_type"],
        entity_id=entry["entity_id"],
        action=entry["action"],
        user_id=None,
        timestamp=datetime.fromisoformat(str(entry["timestamp"])),
        old_values=old_values,
        new_values=new_values,
    )
    assert recomputed == entry["entry_hash"]
