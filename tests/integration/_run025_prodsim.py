"""Reproduce production's tenant-orphan shape on a scratch PostgreSQL database.

Why this exists
---------------
The Run025 remediation scripts are only as good as their behaviour against the
schema and data they will actually meet, and two of the properties that matter
cannot be reproduced on SQLite at all:

* ``tenant_id`` is **nullable** on these five tables in production and **NOT
  NULL** on any freshly migrated database. The July 2026 WCS-TEN2 wave tightened
  each column only when its NULL count was zero, so CI converges and production
  does not. Every orphan this remediation exists for lives in that gap, and a test
  on a freshly migrated database cannot even insert one.
* ``audit_runs``, ``audit_findings``, ``risks_v2`` and ``users`` are under ``FORCE
  ROW LEVEL SECURITY``. Whether a role can see a tenant-less row is the whole
  question, and RLS does not exist in SQLite.

So this module widens the columns, seeds the measured production shape, and leaves
the caller to roll the whole thing back. PostgreSQL makes DDL transactional, so the
``ALTER TABLE ... DROP NOT NULL`` disappears on rollback along with the rows — this
never leaves a shared integration database drifted.

The measured production shape, 2026-07-28
-----------------------------------------
820 tenant-less rows outside the #1398 migration scope::

    external_audit_import_drafts  754
    audit_runs                     37
    external_audit_import_jobs     27
    audit_findings                  1
    risks_v2                        1

816 inherit a tenant from ``david.harris@plantexpand.com`` (active, tenant 1). Four
cannot: two audit runs, one finding and one risk, all created by
``smoke-runner@plantexpand.com`` (deactivated, ``tenant_id`` NULL).

Two further debris rows sit in ``audit_responses``, which is *absent from the list
above* and absent from the backfill's count for a reason worth stating plainly:
``AuditResponse`` does not declare ``tenant_id`` even though the production table
has it, and the backfill enumerates from model metadata. Production holds 315
tenant-less ``audit_responses`` rows that no script in this family can see. This
fixture seeds tenant-less responses deliberately, and the backfill's totals stay at
820/816 with them present — which is the blind spot, observable rather than argued.

Requires a database built by the alembic chain, not by ``Base.metadata.create_all``:
on the latter, ``audit_responses.tenant_id`` does not exist at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import sqlalchemy as sa

# The five tables whose tenant_id the WCS-TEN2 wave failed to tighten on any
# database that held an orphan when it ran.
STILL_NULLABLE_IN_PRODUCTION: tuple[str, ...] = (
    "external_audit_import_drafts",
    "audit_runs",
    "external_audit_import_jobs",
    "audit_findings",
    "risks_v2",
)

# Counts measured on production, reproduced exactly, so the numbers these scripts
# report can be compared against the production dry run rather than to a rounded
# shape that happens to behave the same way.
PRODUCTION_ORPHANS: dict[str, int] = {
    "external_audit_import_drafts": 754,
    "audit_runs": 37,
    "external_audit_import_jobs": 27,
    "audit_findings": 1,
    "risks_v2": 1,
}
TOTAL_ORPHANS = sum(PRODUCTION_ORPHANS.values())

#: Debris rows the backfill can see: the two runs, the finding and the risk.
DEBRIS_ROWS = 4
INHERITABLE_ORPHANS = TOTAL_ORPHANS - DEBRIS_ROWS

#: Debris rows the backfill cannot see, because ``AuditResponse`` declares no
#: ``tenant_id``. Deleted by the purge all the same, and counted in its manifest.
UNDECLARED_DEBRIS_ROWS = 2
REVIEWED_ROWS = DEBRIS_ROWS + UNDECLARED_DEBRIS_ROWS

#: Genuine responses, spread over three of the surviving runs. Production's real runs
#: carry 3 to 58 responses each; the two debris runs carry exactly one apiece.
GENUINE_RESPONSES_PER_RUN: tuple[int, ...] = (3, 5, 8)

#: What the smoke test wrote in ``notes``, and the marker the reviewed set turns on.
RESPONSE_MARKER = "E2E response"

SMOKE_EMAIL = "smoke-runner@plantexpand.com"
OWNER_EMAIL = "david.harris@plantexpand.com"

#: Jobs that actually carry drafts. 754 drafts across 16 of the 27 jobs, measured.
POPULATED_JOBS = 16

# The orphans were created in March 2026. Ages are an offset from "now" rather than
# fixed dates, so the backfill's max-orphan-age check keeps seeing them as
# historical however long this harness lives.
_ORPHAN_AGE = timedelta(days=120)


@dataclass(frozen=True)
class SeededShape:
    """Identifiers needed to address what was seeded.

    Real primary keys rather than production's 5, 6, 4 and 2: an integration
    database is shared with every other test in the job and cannot be made to yield
    a chosen id. The production identifiers are pinned separately, as a literal, in
    ``purge_reviewed_debris_rows.REVIEWED_DEBRIS``, and a unit test checks that
    literal has not been edited.
    """

    unique: str
    tenant_id: int
    smoke_user_id: int
    smoke_email: str
    owner_user_id: int
    reference_base: int
    debris_run_ids: tuple[int, int]
    debris_finding_id: int
    debris_risk_id: int
    debris_response_ids: tuple[int, int]
    inheritable_run_ids: tuple[int, ...]
    question_ids: tuple[int, ...]
    genuine_response_ids: tuple[int, ...]
    job_ids: tuple[int, ...]
    draft_ids: tuple[int, ...]

    @property
    def debris_keys(self) -> tuple[tuple[str, int], ...]:
        return (
            ("audit_runs", self.debris_run_ids[0]),
            ("audit_runs", self.debris_run_ids[1]),
            ("audit_findings", self.debris_finding_id),
            ("risks_v2", self.debris_risk_id),
            ("audit_responses", self.debris_response_ids[0]),
            ("audit_responses", self.debris_response_ids[1]),
        )


async def relax_tenant_not_null(conn: Any) -> list[str]:
    """Reproduce production's schema drift: ``tenant_id`` nullable on the five tables.

    Returns the tables it actually widened, so a caller can assert it had something
    to widen rather than silently testing a schema that was already relaxed.
    """
    widened: list[str] = []
    for table in STILL_NULLABLE_IN_PRODUCTION:
        nullable = (
            await conn.execute(
                sa.text(
                    "SELECT is_nullable = 'YES' FROM information_schema.columns "
                    "WHERE table_schema = current_schema() AND table_name = :table AND column_name = 'tenant_id'"
                ),
                {"table": table},
            )
        ).scalar()
        if nullable is False:
            await conn.execute(sa.text(f"ALTER TABLE {table} ALTER COLUMN tenant_id DROP NOT NULL"))
            widened.append(table)
    return widened


async def _insert(conn: Any, table: str, values: dict[str, Any]) -> int:
    columns = ", ".join(values)
    placeholders = ", ".join(f":{name}" for name in values)
    return int(
        (
            await conn.execute(
                sa.text(f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id"),  # noqa: S608
                values,
            )
        ).scalar()
    )


async def _ensure_single_active_tenant(conn: Any) -> int:
    """Leave exactly one active tenant, creating one if the database has none.

    ``backfill_tenant_orphan_rows`` derives its blanket default from there being
    exactly one active tenant and refuses otherwise. A shared integration database
    may hold tenants other tests created, so the precondition is established rather
    than hoped for — and the caller's rollback undoes it.
    """
    existing = (await conn.execute(sa.text("SELECT id FROM tenants WHERE is_active ORDER BY id LIMIT 1"))).scalar()
    tenant_id = (
        int(existing)
        if existing is not None
        else await _insert(
            conn,
            "tenants",
            {
                "name": "Default Organisation",
                "slug": "default-organisation",
                "admin_email": "admin@plantexpand.com",
            },
        )
    )
    await conn.execute(sa.text("UPDATE tenants SET is_active = false WHERE id <> :keep"), {"keep": tenant_id})
    return tenant_id


async def _user(conn: Any, *, email: str, is_active: bool, tenant_id: Optional[int]) -> int:
    return await _insert(
        conn,
        "users",
        {
            "email": email,
            "hashed_password": "not-a-real-hash",
            "first_name": "Seeded",
            "last_name": "User",
            "is_active": is_active,
            "is_superuser": False,
            "tenant_id": tenant_id,
        },
    )


async def _require_tenant_column(conn: Any, table: str) -> None:
    """Refuse to seed a table whose ``tenant_id`` this database does not have.

    ``audit_responses``, ``audit_questions`` and ``audit_sections`` carry
    ``tenant_id`` in production but their models do not declare it, so a database
    built by ``Base.metadata.create_all`` — which is how the integration suite builds
    its schema — has no such column. Seeding into it would fail with a driver error
    several frames from the cause, so the cause is stated here instead.
    """
    present = (
        await conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() "
                "AND table_name = :table AND column_name = 'tenant_id'"
            ),
            {"table": table},
        )
    ).scalar()
    if present is None:
        raise RuntimeError(
            f"{table} has no tenant_id column in this database. This fixture reproduces production, "
            "which has one; a schema built from model metadata does not, because the model does not "
            "declare it. Build the database with the alembic chain."
        )


async def _questions(conn: Any, *, template_id: int, unique: str) -> tuple[int, ...]:
    """One section and eight questions, enough for the busiest genuine run seeded.

    ``uq_audit_responses_run_question`` is UNIQUE on ``(run_id, question_id)``, so a
    run with eight responses needs eight distinct questions.
    """
    section_id = await _insert(
        conn,
        "audit_sections",
        {
            "template_id": template_id,
            "title": f"Seeded section {unique or 'prodsim'}",
            "sort_order": 1,
            "weight": 1.0,
            "is_repeatable": False,
            "is_active": True,
        },
    )
    return tuple(
        [
            await _insert(
                conn,
                "audit_questions",
                {
                    "template_id": template_id,
                    "section_id": section_id,
                    "question_text": f"Seeded question {index + 1}?",
                    "question_type": "yes_no",
                    "is_required": True,
                    "allow_na": False,
                    "is_active": True,
                    "max_score": 1.0,
                    "weight": 1.0,
                    "sort_order": index + 1,
                },
            )
            for index in range(max(GENUINE_RESPONSES_PER_RUN))
        ]
    )


async def seed_production_shape(
    conn: Any,
    *,
    unique: str = "",
    reference_base: int = 0,
    link_risk_to_finding: bool = False,
    point_a_draft_at_debris_run: bool = False,
    surviving_finding_above_the_debris_one: bool = False,
    surviving_risk_above_the_debris_one: bool = False,
) -> SeededShape:
    """Seed 820 tenant-less rows matching production, and return their keys.

    ``reference_base`` is added to every sequential suffix. Left at 0 the references
    come out as production's own — ``AUD-2026-0005``, ``AUD-2026-0006``,
    ``FND-2026-0001``, ``RSK-2026-0002`` — which is what makes the reference
    arithmetic directly comparable. On a shared database those are already taken, so
    the caller offsets them; the arithmetic is unaffected by the offset because it is
    computed from the rows present, not from the literal numbers.

    ``link_risk_to_finding`` inserts the ``audit_finding_risks`` junction row that
    ``AuditService._link_risk_to_finding`` writes when a finding is escalated into
    the risk register. That row cascades from *both* parents and is not itself in the
    reviewed set, which is how the out-of-set cascade refusal is constructed.

    ``point_a_draft_at_debris_run`` attaches one of the 754 import drafts — real user
    work by an active user — to a debris audit run.
    ``external_audit_import_drafts.audit_run_id`` is ``ON DELETE CASCADE``, so this
    is the worst realistic outcome available: deleting a smoke-test audit run
    silently destroying a genuine draft.

    ``surviving_finding_above_the_debris_one`` and
    ``surviving_risk_above_the_debris_one`` add an attributed finding and risk with
    higher references, which is what makes each sequence survive the delete. That is
    the difference between a reference-reuse hazard and no hazard. Left off, the
    reproduction is the pessimistic case — the debris row is the only row in its
    table, so deleting it resets the sequence. Production turned out to be the other
    case, with 204 findings and 204 risks either side, measured by the dry run there:
    both come back safe. Turn these on to reproduce production; leave them off to
    watch the reference-reuse refusal fire.
    """
    created = datetime.now(timezone.utc) - _ORPHAN_AGE
    suffix = f"{reference_base:d}" if reference_base else ""

    tenant_id = await _ensure_single_active_tenant(conn)
    smoke_email = f"{unique}{SMOKE_EMAIL}" if unique else SMOKE_EMAIL
    smoke_user_id = await _user(conn, email=smoke_email, is_active=False, tenant_id=None)
    owner_user_id = await _user(
        conn, email=f"{unique}{OWNER_EMAIL}" if unique else OWNER_EMAIL, is_active=True, tenant_id=tenant_id
    )

    template_id = await _insert(
        conn,
        "audit_templates",
        {
            "name": f"Seeded template {unique or 'prodsim'}",
            "audit_type": "internal",
            "version": 1,
            "is_active": True,
            "is_published": True,
            "scoring_method": "percentage",
            "allow_offline": False,
            "require_gps": False,
            "require_signature": False,
            "require_approval": False,
            "auto_create_findings": False,
            "reference_number": f"TPL-2026-{reference_base + 1:04d}",
            "external_id": f"tpl-{unique or 'prodsim'}{suffix}",
            # Deliberately tenant-less, and this is the single most important detail
            # in the whole fixture. ``AuditTemplate.tenant_id`` is declared
            # ``nullable=True`` in the ORM, so ``audit_templates`` is not in
            # ``tenant_required_tables()`` and therefore not in the backfill's scope
            # or the inventory's — a tenant-less template is counted nowhere. That is
            # what makes ``PROVENANCE_RULES["audit_runs"]``'s first rule
            # (template_id -> audit_templates) inert in production, and it is why the
            # 35 genuine orphan runs inherit from *the user who created them* rather
            # than from their template, exactly as measured. Give the template a
            # tenant here and all 37 runs inherit, the debris runs included, and the
            # fixture stops reproducing the thing under test.
            "tenant_id": None,
        },
    )
    evidence_asset_id = await _insert(
        conn,
        "evidence_assets",
        {
            "storage_key": f"seed/{unique or 'prodsim'}{suffix}.pdf",
            "content_type": "application/pdf",
            "source_module": "external_audit_import",
            "source_id": f"{unique or 'prodsim'}{suffix}",
            "tenant_id": tenant_id,
        },
    )

    async def _audit_run(*, minute: int, creator: int, ref_suffix: int, title: str, tenant: Optional[int]) -> int:
        return await _insert(
            conn,
            "audit_runs",
            {
                "template_id": template_id,
                "template_version": 1,
                "status": "completed",
                "reference_number": f"AUD-2026-{reference_base + ref_suffix:04d}",
                "title": title,
                "tenant_id": tenant,
                "created_by_id": creator,
                "created_at": created + timedelta(minutes=minute),
            },
        )

    # The two debris runs carry AUD-2026-0005 and AUD-2026-0006 — the second is the
    # reference the escalated risk's title names.
    debris_run_ids = (
        await _audit_run(minute=0, creator=smoke_user_id, ref_suffix=5, title="E2E Audit 20260327202714", tenant=None),
        await _audit_run(minute=1, creator=smoke_user_id, ref_suffix=6, title="E2E Audit 20260327213101", tenant=None),
    )

    inheritable_run_ids = tuple(
        [
            await _audit_run(
                minute=2 + offset,
                creator=owner_user_id,
                ref_suffix=7 + offset,
                title=f"Genuine audit {offset}",
                tenant=None,
            )
            for offset in range(PRODUCTION_ORPHANS["audit_runs"] - 2)
        ]
    )

    debris_finding_id = await _insert(
        conn,
        "audit_findings",
        {
            "run_id": debris_run_ids[1],
            "title": "E2E smoke finding",
            "description": "Raised by the audit E2E smoke run.",
            "severity": "minor",
            "finding_type": "observation",
            "status": "open",
            "corrective_action_required": False,
            "reference_number": f"FND-2026-{reference_base + 1:04d}",
            "tenant_id": None,
            "created_by_id": smoke_user_id,
            "created_at": created,
        },
    )

    if surviving_finding_above_the_debris_one:
        await _insert(
            conn,
            "audit_findings",
            {
                "run_id": inheritable_run_ids[0],
                "title": "Genuine nonconformance",
                "description": "Raised by an auditor against a real run.",
                "severity": "major",
                "finding_type": "nonconformance",
                "status": "open",
                "corrective_action_required": True,
                "reference_number": f"FND-2026-{reference_base + 9:04d}",
                "tenant_id": tenant_id,
                "created_by_id": owner_user_id,
                "created_at": created + timedelta(days=1),
            },
        )

    debris_risk_id = await _insert(
        conn,
        "risks_v2",
        {
            "reference": f"RSK-2026-{reference_base + 2:04d}",
            "title": (f"Audit escalation: AUD-2026-{reference_base + 6:04d} / FND-2026-{reference_base + 1:04d}"),
            "description": "Escalated automatically from the E2E smoke finding.",
            "category": "operational",
            "inherent_likelihood": 3,
            "inherent_impact": 3,
            "inherent_score": 9,
            "residual_likelihood": 2,
            "residual_impact": 3,
            "residual_score": 6,
            "tenant_id": None,
            "created_by": smoke_user_id,
            "created_at": created.replace(tzinfo=None),
        },
    )

    if surviving_risk_above_the_debris_one:
        await _insert(
            conn,
            "risks_v2",
            {
                "reference": f"RSK-2026-{reference_base + 9:04d}",
                "title": "Genuine operational risk",
                "description": "Raised by a risk owner, nothing to do with the smoke test.",
                "category": "operational",
                "inherent_likelihood": 3,
                "inherent_impact": 3,
                "inherent_score": 9,
                "residual_likelihood": 2,
                "residual_impact": 3,
                "residual_score": 6,
                "tenant_id": tenant_id,
                "created_by": owner_user_id,
                "created_at": (created + timedelta(days=1)).replace(tzinfo=None),
            },
        )

    if link_risk_to_finding:
        await conn.execute(
            sa.text("INSERT INTO audit_finding_risks (audit_finding_id, risk_id) VALUES (:finding_id, :risk_id)"),
            {"finding_id": debris_finding_id, "risk_id": debris_risk_id},
        )

    await _require_tenant_column(conn, "audit_responses")
    question_ids = await _questions(conn, template_id=template_id, unique=unique)

    async def _response(*, run_id: int, question_id: int, notes: str, seconds: int, tenant: Optional[int]) -> int:
        return await _insert(
            conn,
            "audit_responses",
            {
                "run_id": run_id,
                "question_id": question_id,
                "response_value": "yes",
                "is_na": False,
                "score": 1.0,
                "max_score": 1.0,
                "notes": notes,
                # Tenant-less, as production's 315 are. Invisible to the backfill
                # either way, because the model does not declare the column.
                "tenant_id": tenant,
                "created_at": created + timedelta(seconds=seconds),
            },
        )

    # One response per debris run, on the same question, both "yes", both marked —
    # the smoke test asserting a single question, written seconds after its run.
    debris_response_ids = (
        await _response(
            run_id=debris_run_ids[0], question_id=question_ids[0], notes=RESPONSE_MARKER, seconds=2, tenant=None
        ),
        await _response(
            run_id=debris_run_ids[1], question_id=question_ids[0], notes=RESPONSE_MARKER, seconds=63, tenant=None
        ),
    )

    # Genuine answers on genuine runs. Real notes, so a reviewed set that reached one
    # of these would be refused on the marker rather than passing unnoticed.
    genuine_response_ids: list[int] = []
    for run_offset, count in enumerate(GENUINE_RESPONSES_PER_RUN):
        for index in range(count):
            genuine_response_ids.append(
                await _response(
                    run_id=inheritable_run_ids[run_offset],
                    question_id=question_ids[index % len(question_ids)],
                    notes=f"Observed on site, evidence photo {index + 1}",
                    seconds=300 + run_offset * 60 + index,
                    tenant=None,
                )
            )

    # Import jobs and drafts: real work by an active user, hung off the genuine audit
    # runs rather than the debris ones.
    job_ids: list[int] = []
    for index in range(PRODUCTION_ORPHANS["external_audit_import_jobs"]):
        job_ids.append(
            await _insert(
                conn,
                "external_audit_import_jobs",
                {
                    "audit_run_id": inheritable_run_ids[index % len(inheritable_run_ids)],
                    "source_document_asset_id": evidence_asset_id,
                    "tenant_id": None,
                    "source_checksum_sha256": f"{index:064d}",
                    "idempotency_key": f"{unique or 'prodsim'}{suffix}-job-{index}",
                    "reference_number": f"AIM-2026-{reference_base + index + 1:04d}",
                    "created_by_id": owner_user_id,
                    "created_at": created + timedelta(hours=index),
                },
            )
        )

    draft_ids: list[int] = []
    populated_jobs = job_ids[:POPULATED_JOBS]
    for index in range(PRODUCTION_ORPHANS["external_audit_import_drafts"]):
        draft_ids.append(
            await _insert(
                conn,
                "external_audit_import_drafts",
                {
                    "import_job_id": populated_jobs[index % len(populated_jobs)],
                    "audit_run_id": (
                        debris_run_ids[0]
                        if point_a_draft_at_debris_run and index == 0
                        else inheritable_run_ids[index % len(inheritable_run_ids)]
                    ),
                    "tenant_id": None,
                    "title": f"Imported nonconformance {index}",
                    "description": "Extracted from an external audit report.",
                    "created_by_id": owner_user_id,
                    "created_at": created + timedelta(minutes=index),
                },
            )
        )

    return SeededShape(
        unique=unique,
        tenant_id=tenant_id,
        smoke_user_id=smoke_user_id,
        smoke_email=smoke_email,
        owner_user_id=owner_user_id,
        reference_base=reference_base,
        debris_run_ids=debris_run_ids,
        debris_finding_id=debris_finding_id,
        debris_risk_id=debris_risk_id,
        debris_response_ids=debris_response_ids,
        inheritable_run_ids=inheritable_run_ids,
        question_ids=question_ids,
        genuine_response_ids=tuple(genuine_response_ids),
        job_ids=tuple(job_ids),
        draft_ids=tuple(draft_ids),
    )


def reviewed_set_for(shape: SeededShape) -> tuple[Any, ...]:
    """A ``REVIEWED_DEBRIS`` equivalent addressing the rows actually seeded."""
    from scripts.ops.run025.purge_reviewed_debris_rows import ReviewedRow

    return (
        ReviewedRow(
            table="audit_runs",
            row_id=shape.debris_run_ids[0],
            creator_column="created_by_id",
            creator_email=shape.smoke_email,
            evidence='E2E smoke audit run, title "E2E Audit 20260327202714"',
        ),
        ReviewedRow(
            table="audit_runs",
            row_id=shape.debris_run_ids[1],
            creator_column="created_by_id",
            creator_email=shape.smoke_email,
            evidence='E2E smoke audit run, title "E2E Audit 20260327213101"',
        ),
        ReviewedRow(
            table="audit_findings",
            row_id=shape.debris_finding_id,
            creator_column="created_by_id",
            creator_email=shape.smoke_email,
            evidence="finding raised inside one of the two E2E smoke runs above",
        ),
        ReviewedRow(
            table="risks_v2",
            row_id=shape.debris_risk_id,
            creator_column="created_by",
            creator_email=shape.smoke_email,
            evidence="auto-escalation of that finding",
        ),
        ReviewedRow(
            table="audit_responses",
            row_id=shape.debris_response_ids[0],
            parent_column="run_id",
            parent_table="audit_runs",
            parent_row_id=shape.debris_run_ids[0],
            marker_column="notes",
            marker_value=RESPONSE_MARKER,
            evidence="sole response of the first smoke run",
        ),
        ReviewedRow(
            table="audit_responses",
            row_id=shape.debris_response_ids[1],
            parent_column="run_id",
            parent_table="audit_runs",
            parent_row_id=shape.debris_run_ids[1],
            marker_column="notes",
            marker_value=RESPONSE_MARKER,
            evidence="sole response of the second smoke run",
        ),
    )
