"""Title resolution for audit-finding escalations into the enterprise risk register."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditFinding, audit_finding_risks
from src.domain.models.risk_register import EnterpriseRisk

GENERIC_ESCALATION_TITLE_RE = re.compile(
    r"^(?:Audit escalation|Imported audit escalation)\s*:",
    re.IGNORECASE,
)

DESCRIPTION_PREVIEW_CHARS = 120
MAX_RISK_TITLE_LENGTH = 255
MIN_TITLE_FOR_REF_SUFFIX = 15


class FindingTitleSource(Protocol):
    title: str
    description: str
    reference_number: str


def is_generic_audit_escalation_title(title: str | None) -> bool:
    """Return True when the title is a legacy auto-generated escalation label."""
    if not title or not title.strip():
        return False
    return GENERIC_ESCALATION_TITLE_RE.match(title.strip()) is not None


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def _is_weak_finding_title(title: str | None, finding_reference: str) -> bool:
    cleaned = (title or "").strip()
    if not cleaned:
        return True
    if len(cleaned) < 4:
        return True
    return cleaned.casefold() == finding_reference.casefold()


def _description_preview(description: str | None, *, max_chars: int = DESCRIPTION_PREVIEW_CHARS) -> str:
    cleaned = _normalize_whitespace((description or "").strip())
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def _ref_fallback_title(run_reference_number: str, finding_reference_number: str) -> str:
    return f"Audit escalation: {run_reference_number} / {finding_reference_number}"


def _maybe_append_finding_ref_suffix(base_title: str, finding_reference: str) -> str:
    suffix = f" (from {finding_reference})"
    if len(base_title) < MIN_TITLE_FOR_REF_SUFFIX:
        return base_title
    if len(base_title) + len(suffix) > MAX_RISK_TITLE_LENGTH:
        return base_title
    return base_title + suffix


def build_audit_escalation_risk_title(
    *,
    finding: FindingTitleSource,
    run_reference_number: str,
    suggested_title: str | None = None,
) -> str:
    """Build a human-readable risk title from an audit finding escalation."""
    finding_ref = finding.reference_number
    fallback = _ref_fallback_title(run_reference_number, finding_ref)

    base_title: str | None = None
    append_suffix = True
    suggested = (suggested_title or "").strip()
    if suggested and not is_generic_audit_escalation_title(suggested):
        base_title = suggested
        append_suffix = False

    if base_title is None:
        finding_title = (finding.title or "").strip()
        if not _is_weak_finding_title(finding_title, finding_ref):
            base_title = finding_title

    if base_title is None:
        preview = _description_preview(finding.description)
        if preview:
            base_title = preview

    if base_title is None:
        return fallback[:MAX_RISK_TITLE_LENGTH]

    titled = _maybe_append_finding_ref_suffix(base_title, finding_ref) if append_suffix else base_title
    return titled[:MAX_RISK_TITLE_LENGTH]


def upgrade_generic_escalation_title(
    existing_title: str | None,
    *,
    finding: FindingTitleSource,
    run_reference_number: str,
    suggested_title: str | None = None,
) -> str | None:
    """Return a descriptive replacement when *existing_title* is a legacy escalation label."""
    if not is_generic_audit_escalation_title(existing_title):
        return None
    return build_audit_escalation_risk_title(
        finding=finding,
        run_reference_number=run_reference_number,
        suggested_title=suggested_title,
    )


@dataclass
class BackfillTitleChange:
    risk_id: int
    risk_reference: str
    old_title: str
    new_title: str
    finding_reference: str | None
    skipped_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "risk_reference": self.risk_reference,
            "old_title": self.old_title,
            "new_title": self.new_title,
            "finding_reference": self.finding_reference,
            "skipped_reason": self.skipped_reason,
        }


async def _resolve_finding_for_risk(
    db: AsyncSession,
    *,
    tenant_id: int,
    risk: EnterpriseRisk,
) -> AuditFinding | None:
    junction_result = await db.execute(
        select(AuditFinding)
        .join(
            audit_finding_risks,
            audit_finding_risks.c.audit_finding_id == AuditFinding.id,
        )
        .where(
            audit_finding_risks.c.risk_id == risk.id,
            AuditFinding.tenant_id == tenant_id,
        )
        .order_by(AuditFinding.id.asc())
        .limit(1)
    )
    finding = junction_result.scalar_one_or_none()
    if finding is not None:
        return finding

    linked_refs = [ref for ref in (risk.linked_audits or []) if ref]
    if not linked_refs:
        return None

    ref_result = await db.execute(
        select(AuditFinding)
        .where(
            AuditFinding.tenant_id == tenant_id,
            AuditFinding.reference_number.in_(linked_refs),
        )
        .order_by(AuditFinding.id.asc())
        .limit(1)
    )
    return ref_result.scalar_one_or_none()


async def backfill_descriptive_escalation_titles(
    db: AsyncSession,
    tenant_id: int,
    *,
    commit: bool = False,
) -> dict[str, Any]:
    """Rewrite legacy escalation titles using linked audit finding titles."""
    result = await db.execute(
        select(EnterpriseRisk)
        .where(
            EnterpriseRisk.tenant_id == tenant_id,
            EnterpriseRisk.title.ilike("Audit escalation:%")
            | EnterpriseRisk.title.ilike("Imported audit escalation:%"),
        )
        .order_by(EnterpriseRisk.id.asc())
    )
    risks = list(result.scalars().all())

    changes: list[BackfillTitleChange] = []
    skipped: list[BackfillTitleChange] = []
    updated_count = 0

    for risk in risks:
        finding = await _resolve_finding_for_risk(db, tenant_id=tenant_id, risk=risk)
        if finding is None:
            skipped.append(
                BackfillTitleChange(
                    risk_id=risk.id,
                    risk_reference=risk.reference,
                    old_title=risk.title,
                    new_title=risk.title,
                    finding_reference=None,
                    skipped_reason="no_linked_finding",
                )
            )
            continue

        run_ref = ""
        linked = risk.linked_audits or []
        for ref in linked:
            if ref and ref != finding.reference_number:
                run_ref = ref
                break

        new_title = build_audit_escalation_risk_title(
            finding=finding,
            run_reference_number=run_ref or "AUD-UNKNOWN",
        )
        if new_title == risk.title or is_generic_audit_escalation_title(new_title):
            skipped.append(
                BackfillTitleChange(
                    risk_id=risk.id,
                    risk_reference=risk.reference,
                    old_title=risk.title,
                    new_title=new_title,
                    finding_reference=finding.reference_number,
                    skipped_reason="no_improvement",
                )
            )
            continue

        change = BackfillTitleChange(
            risk_id=risk.id,
            risk_reference=risk.reference,
            old_title=risk.title,
            new_title=new_title,
            finding_reference=finding.reference_number,
        )
        changes.append(change)
        if commit:
            risk.title = new_title
            updated_count += 1

    if commit and updated_count:
        await db.commit()

    return {
        "dry_run": not commit,
        "candidate_count": len(risks),
        "would_update_count": len(changes),
        "updated_count": updated_count if commit else 0,
        "changes": [item.to_dict() for item in changes],
        "skipped": [item.to_dict() for item in skipped],
    }
