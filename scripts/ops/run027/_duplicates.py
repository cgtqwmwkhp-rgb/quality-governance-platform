"""One definition of "the same record twice", shared by the scanner and the purge.

Both scripts need it and they must not disagree. The scanner uses it to propose
candidates for review; the purge uses it to answer the question that actually
protects the register — *if I delete these rows, does anything survive to
represent this audit?* If the two used different rules, the purge could report a
survivor the scanner did not think was in the group, or delete a whole group while
reporting that one remained.

Identity is deliberately not "every column"
-------------------------------------------
The twins this was built for, ``AUD-2026-0043`` and ``AUD-2026-0048``, are the same
audit imported twice. They therefore differ in exactly the columns that record *the
import* rather than *the audit*: ``id``, ``reference_number``, ``created_at``,
``completed_at``, and the import job behind them. Including any of those in the
identity would put every duplicate in its own group and find nothing.

So identity is the audit's own content — what it was, who did it, when it was
carried out, what it scored — and the volatile columns are reported alongside as
context, because they are exactly what a human needs in order to choose which row
is the survivor.

Columns are intersected with what the database actually has
----------------------------------------------------------
The candidate lists below are generous, and :func:`resolve` keeps only the columns
the reflected table really has. This repository has documented model/schema drift,
and the registers are genuinely uneven — ``risks_v2`` calls its reference
``reference`` while everything else uses ``reference_number``; ``near_misses`` has
no ``title``. A hardcoded column list would crash on the first register that
disagrees, in the middle of a production scan.

A register that loses so many columns that only a title is left is reported as
unscannable rather than scanned. Grouping on one free-text column alone would
report every "Site inspection" ever raised as a duplicate of every other, and a
report that cries wolf is worse than no report: somebody eventually approves a
delete from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import sqlalchemy as sa

#: Minimum number of identity columns, beyond the tenant, for a group to mean
#: anything. Two — a title plus at least one independent discriminator.
MIN_IDENTITY_COLUMNS = 2


@dataclass(frozen=True)
class RegisterSpec:
    """A register to look for duplicates in."""

    #: What the user calls it.
    name: str
    table: str
    #: Columns that describe the record itself. Order is preserved in the group key.
    identity_candidates: tuple[str, ...]
    #: Columns reported to help a human choose a survivor. Never part of identity.
    context_candidates: tuple[str, ...] = ()
    #: Why this register is grouped the way it is.
    note: str = ""


@dataclass(frozen=True)
class ResolvedRegister:
    """A :class:`RegisterSpec` narrowed to the columns this database really has."""

    spec: RegisterSpec
    table: str
    key_column: str
    reference_column: Optional[str]
    identity_columns: tuple[str, ...]
    context_columns: tuple[str, ...]
    has_tenant: bool
    skipped_columns: tuple[str, ...] = field(default_factory=tuple)

    @property
    def name(self) -> str:
        return self.spec.name


#: The audit register, plus the risk, action and case registers named in FR-DEDUP-01.
#:
#: ``audit_runs`` deliberately excludes ``completed_at`` and ``created_at`` from
#: identity: the twins differ in both, and grouping on them finds nothing. It
#: includes ``template_id`` because the same title against a different template is a
#: different audit, and ``score_percentage`` because two genuine audits of the same
#: thing on the same day almost never score identically — it is the column that
#: turns a plausible group into a near-certain one.
REGISTERS: tuple[RegisterSpec, ...] = (
    RegisterSpec(
        name="audits",
        table="audit_runs",
        identity_candidates=(
            "title",
            "template_id",
            "external_auditor_name",
            "external_reference",
            "score_percentage",
            "source_origin",
            "assurance_scheme",
            "status",
        ),
        context_candidates=(
            "reference_number",
            "created_at",
            "completed_at",
            "scheduled_date",
            "source_document_label",
            "external_body_name",
        ),
        note=(
            "An identical title, template, auditor and score is the signature of the same "
            "report imported twice. created_at/completed_at are context, not identity, "
            "because a re-import necessarily differs in both."
        ),
    ),
    RegisterSpec(
        name="risks",
        table="risks_v2",
        identity_candidates=("title", "category", "description"),
        context_candidates=("reference", "created_at", "status"),
        note="The enterprise risk register. Grouped on title plus category.",
    ),
    RegisterSpec(
        name="risks_legacy",
        table="risks",
        identity_candidates=("title", "risk_level", "description"),
        context_candidates=("reference_number", "created_at", "status"),
        note="The pre-v2 operational risk table, still populated on some tenants.",
    ),
    RegisterSpec(
        name="actions_capa",
        table="capa_actions",
        identity_candidates=("title", "source_type", "source_id", "capa_type", "due_date"),
        context_candidates=("reference_number", "created_at", "status", "assigned_to_id"),
        note=(
            "Two CAPAs with the same title against the same source are the usual result of a "
            "double promotion. source_id is part of identity here, not context: the same title "
            "against a different finding is a different action."
        ),
    ),
    RegisterSpec(
        name="actions_incident",
        table="incident_actions",
        identity_candidates=("title", "incident_id", "due_date", "description"),
        context_candidates=("reference_number", "created_at", "status"),
    ),
    RegisterSpec(
        name="actions_rta",
        table="rta_actions",
        identity_candidates=("title", "rta_id", "due_date", "description"),
        context_candidates=("reference_number", "created_at", "status"),
    ),
    RegisterSpec(
        name="actions_complaint",
        table="complaint_actions",
        identity_candidates=("title", "complaint_id", "due_date", "description"),
        context_candidates=("reference_number", "created_at", "status"),
    ),
    RegisterSpec(
        name="actions_investigation",
        table="investigation_actions",
        identity_candidates=("title", "investigation_id", "due_date", "description"),
        context_candidates=("reference_number", "created_at", "status"),
    ),
    RegisterSpec(
        name="cases_incidents",
        table="incidents",
        identity_candidates=("title", "incident_date", "severity", "location", "description"),
        context_candidates=("reference_number", "created_at", "status"),
    ),
    RegisterSpec(
        name="cases_near_misses",
        table="near_misses",
        identity_candidates=("title", "description", "occurred_at", "severity", "location"),
        context_candidates=("reference_number", "created_at", "status"),
    ),
    RegisterSpec(
        name="cases_complaints",
        table="complaints",
        identity_candidates=("title", "description", "complainant_name", "received_at"),
        context_candidates=("reference_number", "created_at", "status"),
    ),
    RegisterSpec(
        name="cases_rta",
        table="road_traffic_collisions",
        identity_candidates=("title", "description", "collision_date", "severity", "vehicle_registration"),
        context_candidates=("reference_number", "created_at", "status"),
    ),
)

#: Reference column names, in the order ``ReferenceNumberService`` tries them.
REFERENCE_COLUMNS: tuple[str, ...] = ("reference_number", "reference")


def resolve(sync_session: Any, specs: Sequence[RegisterSpec]) -> tuple[list[ResolvedRegister], list[dict[str, Any]]]:
    """Narrow each spec to this database's columns. Returns ``(usable, skipped)``.

    A missing table is a normal answer, not an error: these scripts run against
    production, staging and the SQLite the tests use, and those do not hold the same
    set of registers.
    """
    inspector = sa.inspect(sync_session.get_bind())
    present = set(inspector.get_table_names())

    usable: list[ResolvedRegister] = []
    skipped: list[dict[str, Any]] = []

    for spec in specs:
        if spec.table not in present:
            skipped.append({"register": spec.name, "table": spec.table, "reason": "table not present"})
            continue

        columns = {column["name"] for column in inspector.get_columns(spec.table)}
        keys = inspector.get_pk_constraint(spec.table).get("constrained_columns") or []
        if len(keys) != 1:
            skipped.append(
                {
                    "register": spec.name,
                    "table": spec.table,
                    "reason": "no single-column primary key, so duplicate rows cannot be identified individually",
                }
            )
            continue

        identity = tuple(column for column in spec.identity_candidates if column in columns)
        missing = tuple(column for column in spec.identity_candidates if column not in columns)
        if len(identity) < MIN_IDENTITY_COLUMNS:
            skipped.append(
                {
                    "register": spec.name,
                    "table": spec.table,
                    "reason": (
                        f"only {len(identity)} of the {len(spec.identity_candidates)} identity columns exist "
                        f"({', '.join(identity) or 'none'}); grouping on that would report unrelated records "
                        "as duplicates"
                    ),
                    "missing_columns": list(missing),
                }
            )
            continue

        usable.append(
            ResolvedRegister(
                spec=spec,
                table=spec.table,
                key_column=keys[0],
                reference_column=next((column for column in REFERENCE_COLUMNS if column in columns), None),
                identity_columns=identity,
                context_columns=tuple(column for column in spec.context_candidates if column in columns),
                has_tenant="tenant_id" in columns,
                skipped_columns=missing,
            )
        )

    return usable, skipped


def _normalise(value: Any) -> Any:
    """Collapse the differences that should not split a group.

    Case and surrounding whitespace only. Nothing cleverer: stripping punctuation or
    collapsing inner whitespace would merge ``"Gate 3 check"`` with ``"Gate 3 - check"``,
    which are plausibly different audits, and this feeds a delete review.

    ``None`` is preserved as itself rather than becoming ``""``, so "no auditor
    recorded" and "auditor recorded as empty string" stay distinguishable.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    return value


def identity_key(row: dict[str, Any], register: ResolvedRegister) -> tuple[Any, ...]:
    """The group key for one row: its tenant, then its identity columns in order."""
    tenant = row.get("tenant_id") if register.has_tenant else None
    return (tenant, *(_normalise(row.get(column)) for column in register.identity_columns))


async def fetch_rows(
    db: Any,
    register: ResolvedRegister,
    *,
    tenant_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Every row of a register, projected to the columns duplicate detection needs."""
    wanted = [register.key_column, *register.identity_columns, *register.context_columns]
    if register.has_tenant and "tenant_id" not in wanted:
        wanted.append("tenant_id")
    if register.reference_column and register.reference_column not in wanted:
        wanted.append(register.reference_column)

    # Column and table names come from the inspector; the tenant filter is bound.
    projection = ", ".join(dict.fromkeys(wanted))
    sql = f"SELECT {projection} FROM {register.table}"  # noqa: S608
    params: dict[str, Any] = {}
    if tenant_id is not None and register.has_tenant:
        sql += " WHERE tenant_id = :tenant_id"
        params["tenant_id"] = tenant_id
    sql += f" ORDER BY {register.key_column}"

    rows = (await db.execute(sa.text(sql), params)).mappings().all()
    return [dict(row) for row in rows]


def group_duplicates(
    rows: Sequence[dict[str, Any]],
    register: ResolvedRegister,
    *,
    min_group_size: int = 2,
) -> list[dict[str, Any]]:
    """Groups of rows sharing an identity, largest first.

    Rows whose entire identity is null are dropped. They group with each other for
    no reason other than being empty, and reporting "these forty blank drafts are
    duplicates of one another" buries the two rows that matter.
    """
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = identity_key(row, register)
        if all(part is None for part in key[1:]):
            continue
        groups.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for key, members in groups.items():
        if len(members) < min_group_size:
            continue
        out.append(
            {
                "register": register.name,
                "table": register.table,
                "tenant_id": key[0],
                "identity": dict(zip(register.identity_columns, key[1:])),
                "count": len(members),
                "members": [
                    {
                        "id": member[register.key_column],
                        **({"reference": member.get(register.reference_column)} if register.reference_column else {}),
                        **{column: member.get(column) for column in register.context_columns},
                    }
                    for member in members
                ],
            }
        )

    out.sort(key=lambda group: (-group["count"], str(group["table"]), str(group["identity"])))
    return out
