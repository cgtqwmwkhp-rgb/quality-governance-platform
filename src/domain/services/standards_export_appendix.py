"""SG-D-05: audit-pack appendix of SoR pointers for filtered frameworks.

Read-model only. Composes existing SoRs — compliance evidence links, audit
findings, CAPA actions, and the assurance certificate shelf — into one appendix
on ``GET /api/v1/compliance/audit-pack``.

Does **not** call ``get_cell`` / ``get_matrix`` (D2 lock — no cell-aggregate fork).
Bare clause tokens stay unattributed. Unmatched register certs (PAT, insurance)
are never claimed as framework proof.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditFinding
from src.domain.models.capa import CAPAAction
from src.domain.models.compliance_evidence import ComplianceEvidenceLink
from src.domain.services.assurance_cert_shelf_service import AssuranceCertShelfService
from src.domain.services.standards_cell_aggregate_service import (
    FRAMEWORK_ALIASES,
    REGISTER_SHELF_SCHEME,
    framework_for_certificate,
)
from src.domain.services.standards_trap_guard import (
    ALIGNMENT_FRAMEWORK_IDS,
    clause_number_from_token,
    framework_from_clause_token,
)

APPENDIX_VERSION = "sg-d05-1.0"
SCAN_LIMIT = 2000
ROW_LIMIT = 200

PROGRAMME_FRAMEWORKS: tuple[str, ...] = ALIGNMENT_FRAMEWORK_IDS

SOR_NOTE = (
    "Read-model appendix — Audits/Findings, Actions, compliance_evidence_links, "
    "and the certificate shelf remain systems of record. Pointers only; no second library."
)


def _status(value: Any) -> str:
    if value is None:
        return ""
    return str(value.value) if hasattr(value, "value") else str(value)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def normalize_framework_ids(requested: Optional[Iterable[str]]) -> list[str]:
    """Keep programme ids only. Empty/None → the full Constructionline-free set."""
    allowed = set(PROGRAMME_FRAMEWORKS)
    if not requested:
        return list(PROGRAMME_FRAMEWORKS)
    seen: set[str] = set()
    out: list[str] = []
    for raw in requested:
        fw = str(raw or "").strip().lower()
        if fw not in allowed or fw in seen:
            continue
        seen.add(fw)
        out.append(fw)
    return out or list(PROGRAMME_FRAMEWORKS)


def action_tokens(*, clause_reference: Any, iso_standard: Any) -> list[str]:
    """Same tokenisation the workspace uses for CAPA rows — no TrapGuard here."""
    tokens: list[str] = []
    ref = str(clause_reference or "").strip()
    iso = str(iso_standard or "").strip()
    if ref:
        tokens.extend(part.strip() for part in ref.replace(";", ",").split(",") if part.strip())
    if iso and ref:
        tokens.append(f"{iso}-{ref}")
    elif iso:
        tokens.append(iso)
    return tokens


def first_matching_cell(
    tokens: Iterable[Any],
    allowed: set[str],
) -> tuple[Optional[str], str, str]:
    """Return (framework, clause, fate) for the first token that names an allowed framework.

    fate is ``match`` | ``other_framework`` | ``unattributed``.
    """
    saw_other = False
    for token in tokens:
        framework = framework_from_clause_token(token)
        clause = clause_number_from_token(token)
        if not clause and token is not None:
            clause = str(token).strip()
        if framework is None:
            continue
        if framework in allowed:
            return framework, clause, "match"
        saw_other = True
    return None, "", "other_framework" if saw_other else "unattributed"


def partition_by_frameworks(
    rows: list[dict[str, Any]],
    allowed: set[str],
) -> tuple[list[dict[str, Any]], int, int]:
    """Keep rows whose tokens declare an allowed framework. Count the rest honestly."""
    matched: list[dict[str, Any]] = []
    unattributed = 0
    other_framework = 0
    for row in rows:
        framework, clause, fate = first_matching_cell(row.get("tokens") or [], allowed)
        if fate == "match":
            matched.append({**row, "framework": framework, "clause_number": clause})
        elif fate == "unattributed":
            unattributed += 1
        else:
            other_framework += 1
    return matched, unattributed, other_framework


def cap_rows(rows: list[dict[str, Any]], *, limit: int = ROW_LIMIT) -> tuple[list[dict[str, Any]], bool]:
    if len(rows) <= limit:
        return rows, False
    return rows[:limit], True


def cert_framework_for_item(item: dict[str, Any]) -> Optional[str]:
    """Map a shelf item onto a programme framework, or None when unmatched (PAT/insurance)."""
    scheme = str(item.get("scheme") or "").strip().lower()
    if scheme == REGISTER_SHELF_SCHEME:
        metadata = item.get("metadata") or {}
        return framework_for_certificate(metadata.get("certificate_type"), item.get("name"))
    for framework, alias in FRAMEWORK_ALIASES.items():
        schemes = {str(s).lower() for s in alias.get("cert_schemes") or ()}
        if scheme in schemes:
            return framework
    return None


def partition_certs(
    items: list[dict[str, Any]],
    allowed: set[str],
    *,
    include_unmatched: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    omitted_other = 0
    for item in items:
        framework = cert_framework_for_item(item)
        if framework is None:
            if include_unmatched:
                unmatched.append(
                    {
                        "id": item.get("shelf_key") or item.get("reference_number"),
                        "title": item.get("name"),
                        "status": item.get("readiness_status"),
                        "scheme": item.get("scheme"),
                        "expiry_date": item.get("expiry_date"),
                        "detail_path": item.get("detail_path") or "/compliance-schedule?view=certificates",
                        "proof_scope": "unmatched",
                        "framework": None,
                    }
                )
            continue
        if framework not in allowed:
            omitted_other += 1
            continue
        matched.append(
            {
                "id": item.get("shelf_key") or item.get("reference_number"),
                "title": item.get("name"),
                "status": item.get("readiness_status"),
                "scheme": item.get("scheme"),
                "expiry_date": item.get("expiry_date"),
                "detail_path": item.get("detail_path") or "/compliance-schedule?view=certificates",
                "proof_scope": "framework",
                "framework": framework,
            }
        )
    return matched, unmatched, omitted_other


def _pointer(
    *,
    record_id: Any,
    title: Any,
    status: Any,
    framework: Optional[str],
    clause_number: str,
    detail_path: str,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    row = {
        "id": record_id,
        "title": title,
        "status": status,
        "framework": framework,
        "clause_number": clause_number or None,
        "detail_path": detail_path,
    }
    if extra:
        row.update(extra)
    return row


class StandardsExportAppendixService:
    """Compose the D5 appendix for one tenant."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.cert_shelf = AssuranceCertShelfService(db)

    async def build(
        self,
        *,
        tenant_id: int,
        frameworks: Optional[Iterable[str]] = None,
        now: Optional[datetime] = None,
    ) -> dict[str, Any]:
        selected = normalize_framework_ids(frameworks)
        allowed = set(selected)
        include_unmatched = set(selected) == set(PROGRAMME_FRAMEWORKS)
        reference = now or datetime.now(timezone.utc)

        evidence_rows, evidence_scan_truncated = await self._load_evidence(tenant_id)
        finding_rows, findings_scan_truncated = await self._load_findings(tenant_id)
        action_rows, actions_scan_truncated = await self._load_actions(tenant_id)
        shelf = await self.cert_shelf.get_shelf(tenant_id=tenant_id, now=reference)

        evidence, evidence_unattr, evidence_other = partition_by_frameworks(evidence_rows, allowed)
        findings, findings_unattr, findings_other = partition_by_frameworks(finding_rows, allowed)
        actions, actions_unattr, actions_other = partition_by_frameworks(action_rows, allowed)
        certs, unmatched_certs, certs_other = partition_certs(
            list(shelf.get("items") or []),
            allowed,
            include_unmatched=include_unmatched,
        )

        evidence_out, evidence_capped = cap_rows(evidence)
        findings_out, findings_capped = cap_rows(findings)
        actions_out, actions_capped = cap_rows(actions)
        certs_out, certs_capped = cap_rows(certs)
        unmatched_out, unmatched_capped = cap_rows(unmatched_certs)

        return {
            "version": APPENDIX_VERSION,
            "generated_at": reference.isoformat(),
            "frameworks": selected,
            "sor_note": SOR_NOTE,
            "evidence": {
                "items": [
                    _pointer(
                        record_id=row["id"],
                        title=row.get("title"),
                        status=row.get("status"),
                        framework=row.get("framework"),
                        clause_number=row.get("clause_number") or "",
                        detail_path=row.get("detail_path") or "/compliance",
                        extra={
                            "entity_type": row.get("entity_type"),
                            "entity_id": row.get("entity_id"),
                            "clause_id": row.get("clause_id"),
                        },
                    )
                    for row in evidence_out
                ],
                "truncated": evidence_scan_truncated or evidence_capped,
                "unattributed": evidence_unattr,
                "other_framework": evidence_other,
            },
            "findings": {
                "items": [
                    _pointer(
                        record_id=row["id"],
                        title=row.get("title"),
                        status=row.get("status"),
                        framework=row.get("framework"),
                        clause_number=row.get("clause_number") or "",
                        detail_path=row.get("detail_path") or f"/audits?view=findings&findingId={row['id']}",
                        extra={"reference_number": row.get("reference_number")},
                    )
                    for row in findings_out
                ],
                "truncated": findings_scan_truncated or findings_capped,
                "unattributed": findings_unattr,
                "other_framework": findings_other,
            },
            "actions": {
                "items": [
                    _pointer(
                        record_id=row["id"],
                        title=row.get("title"),
                        status=row.get("status"),
                        framework=row.get("framework"),
                        clause_number=row.get("clause_number") or "",
                        detail_path=row.get("detail_path") or f"/actions/{row['id']}",
                        extra={
                            "reference_number": row.get("reference_number"),
                            "due_date": row.get("due_date"),
                        },
                    )
                    for row in actions_out
                ],
                "truncated": actions_scan_truncated or actions_capped,
                "unattributed": actions_unattr,
                "other_framework": actions_other,
            },
            "certs": {
                "items": certs_out,
                "unmatched": unmatched_out,
                "truncated": certs_capped or unmatched_capped,
                "unmatched_included": include_unmatched,
                "other_framework": certs_other,
            },
            "limits": {
                "scan": SCAN_LIMIT,
                "rows": ROW_LIMIT,
            },
        }

    async def _load_evidence(self, tenant_id: int) -> tuple[list[dict[str, Any]], bool]:
        result = await self.db.execute(
            select(ComplianceEvidenceLink)
            .where(
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.deleted_at.is_(None),
            )
            .order_by(ComplianceEvidenceLink.created_at.desc())
            .limit(SCAN_LIMIT)
        )
        rows = list(result.scalars().all())
        payload = [
            {
                "id": link.id,
                "title": link.title,
                "status": _status(link.effective_status if hasattr(link, "effective_status") else link.status),
                "tokens": [link.clause_id] if link.clause_id else [],
                "clause_id": link.clause_id,
                "entity_type": link.entity_type,
                "entity_id": link.entity_id,
                "detail_path": "/compliance",
            }
            for link in rows
        ]
        return payload, len(rows) >= SCAN_LIMIT

    async def _load_findings(self, tenant_id: int) -> tuple[list[dict[str, Any]], bool]:
        result = await self.db.execute(
            select(AuditFinding)
            .where(AuditFinding.tenant_id == tenant_id)
            .order_by(AuditFinding.created_at.desc())
            .limit(SCAN_LIMIT)
        )
        rows = list(result.scalars().all())
        payload = [
            {
                "id": finding.id,
                "title": finding.title,
                "status": _status(finding.status),
                "reference_number": finding.reference_number,
                "tokens": list(finding.clause_ids_json_legacy or []),
                "detail_path": f"/audits?view=findings&findingId={finding.id}",
            }
            for finding in rows
        ]
        return payload, len(rows) >= SCAN_LIMIT

    async def _load_actions(self, tenant_id: int) -> tuple[list[dict[str, Any]], bool]:
        result = await self.db.execute(
            select(CAPAAction)
            .where(CAPAAction.tenant_id == tenant_id)
            .order_by(CAPAAction.created_at.desc())
            .limit(SCAN_LIMIT)
        )
        rows = list(result.scalars().all())
        payload = [
            {
                "id": action.id,
                "title": action.title,
                "status": _status(action.status),
                "reference_number": action.reference_number,
                "due_date": _iso(action.due_date),
                "tokens": action_tokens(
                    clause_reference=action.clause_reference,
                    iso_standard=action.iso_standard,
                ),
                "detail_path": f"/actions/{action.id}",
            }
            for action in rows
        ]
        return payload, len(rows) >= SCAN_LIMIT


async def build_standards_export_appendix(
    db: AsyncSession,
    *,
    tenant_id: int,
    frameworks: Optional[Iterable[str]] = None,
) -> dict[str, Any]:
    return await StandardsExportAppendixService(db).build(tenant_id=tenant_id, frameworks=frameworks)
