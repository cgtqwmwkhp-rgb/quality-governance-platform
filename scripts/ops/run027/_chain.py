"""Record the purge in the tenant's hash-chained audit trail.

``purge_tenant_orphan_rows`` deliberately does *not* write to ``audit_log_entries``,
and its module docstring explains why: the rows it deletes belong to no tenant, and
``audit_log_entries.tenant_id`` is ``NOT NULL``, so recording the deletion would
mean inventing an attribution.

That argument does not apply here and the conclusion inverts. These audits belong
to a real tenant, so the per-tenant chain is writable, and what is being destroyed
is a completed audit with a score and findings — exactly the class of record an
external auditor is entitled to ask about. "Where did AUD-2026-0048 go?" must have
an answer in the register itself, not only in a JSON file on somebody's laptop. So
the purge writes an entry, and it writes it **inside the same transaction as the
deletes**: if the entry cannot be written the deletes roll back, because an
unrecorded destruction of an audit record is the outcome this is meant to prevent.

Two things are borrowed rather than restated:

* ``AuditLogEntry`` itself, via the ORM, so every ``NOT NULL`` column with a
  Python-side default (``action_category``, ``entry_metadata``, ``is_sensitive``,
  ``retention_days``) is populated by the model rather than by a raw ``INSERT``
  that would have to list them and would drift the first time one changed.
* The chaining rule from ``AuditLogService.log`` — ``sequence + 1`` and the
  previous ``entry_hash``, genesis being sixty-four zeroes. Recomputing it here
  would be a second implementation of the one thing in this schema that is
  supposed to have exactly one.

Concurrency
-----------
``(tenant_id, sequence)`` carries no unique constraint, so two writers that read
the same tail both write the same sequence and the chain forks. The application
races this script the moment anyone saves anything for that tenant. On PostgreSQL
the read-and-append is therefore taken under a transaction-scoped advisory lock, the
same device ``ReferenceNumberService`` uses to serialise reference minting; the lock
is released by commit or rollback. On any other dialect the lock is skipped, which
is safe for the single-connection SQLite the tests use and is one more reason the
runbook asks for a maintenance window rather than trusting this alone.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

import sqlalchemy as sa

#: ``AuditLogService.GENESIS_HASH``. First entry in a tenant's chain links to this.
GENESIS_HASH = "0" * 64

#: Namespace for the advisory lock, so it cannot collide with the reference-number
#: locks taken by ``ReferenceNumberService`` on the same database.
_LOCK_NAMESPACE = "run027:audit_log_chain"


def _advisory_lock_key(tenant_id: int) -> int:
    """A stable signed 64-bit key for one tenant's chain."""
    digest = hashlib.sha256(f"{_LOCK_NAMESPACE}:{tenant_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


async def _lock_chain(db: Any, tenant_id: int) -> bool:
    """Serialise appends for this tenant. Returns whether a lock was actually taken."""
    bind = db.get_bind() if hasattr(db, "get_bind") else None
    dialect = getattr(getattr(bind, "dialect", None), "name", None)
    if dialect != "postgresql":
        return False
    await db.execute(sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": _advisory_lock_key(tenant_id)})
    return True


async def record_purge(
    db: Any,
    *,
    tenant_id: int,
    references: list[str],
    old_values: dict[str, Any],
    metadata: dict[str, Any],
    actor_email: Optional[str] = None,
    remediation: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append one ``delete`` entry describing the purge. Does not commit.

    ``old_values`` carries the audit rows as they were, so the entry is not merely a
    note that something was deleted but a record of what. The caller passes the same
    snapshot it writes to the manifest.

    ``remediation`` (CEL remaps/withdrawals, CAPA reassignments) is merged into
    ``new_values``, not ``entry_metadata``. ``AuditLogEntry.compute_hash`` covers
    ``old_values``/``new_values`` and *not* ``entry_metadata``, so putting the row
    mutations in metadata would leave them outside the hash chain.
    """
    from src.domain.models.audit_log import AuditLogEntry

    locked = await _lock_chain(db, tenant_id)

    tail = (
        await db.execute(
            sa.select(AuditLogEntry.sequence, AuditLogEntry.entry_hash)
            .where(AuditLogEntry.tenant_id == tenant_id)
            .order_by(AuditLogEntry.sequence.desc())
            .limit(1)
        )
    ).first()

    if tail is None:
        sequence, previous_hash = 1, GENESIS_HASH
    else:
        sequence, previous_hash = tail[0] + 1, tail[1]

    # TIMESTAMP WITHOUT TIME ZONE — the column is naive UTC and asyncpg rejects
    # aware values, so this matches AuditLogService.log exactly.
    timestamp = datetime.now(timezone.utc).replace(tzinfo=None)

    entity_id = ",".join(references)
    new_values: dict[str, Any] = {"purged": True, "references": references}
    if remediation:
        new_values["remediation"] = remediation

    entry_hash = AuditLogEntry.compute_hash(
        sequence=sequence,
        previous_hash=previous_hash,
        entity_type="audit_run",
        entity_id=entity_id,
        action="delete",
        user_id=None,
        timestamp=timestamp,
        old_values=old_values,
        new_values=new_values,
    )
    entry = AuditLogEntry(
        tenant_id=tenant_id,
        sequence=sequence,
        entry_hash=entry_hash,
        previous_hash=previous_hash,
        entity_type="audit_run",
        entity_id=entity_id,
        entity_name=", ".join(references),
        action="delete",
        action_category="admin",
        old_values=old_values,
        new_values=new_values,
        changed_fields=["*"],
        user_id=None,
        user_email=actor_email,
        user_name="run027 purge_duplicate_audit_runs",
        entry_metadata=metadata,
        timestamp=timestamp,
        is_sensitive=False,
    )
    db.add(entry)
    await db.flush()

    return {
        "sequence": sequence,
        "entry_hash": entry_hash,
        "previous_hash": previous_hash,
        "advisory_lock_taken": locked,
    }
