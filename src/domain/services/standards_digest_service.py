"""Standards hygiene digests for Compliance Automation Monitoring (Wave 3 PR-F3).

Read-model only. Composes existing SoRs — findings, compliance evidence links,
document tips, and the assurance certificate shelf — into one Monitoring payload.

Does **not** call ``get_matrix_summary`` / ``get_cell`` (N+1). Clause attribution
uses the framework declared on each token so bare numbers stay unattributed.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditFinding
from src.domain.models.compliance_evidence import (
    ComplianceEvidenceLink,
    EvidenceLinkMethod,
    EvidenceLinkStatus,
)
from src.domain.models.document import Document, DocumentVersion
from src.domain.services.assurance_cert_shelf_service import AssuranceCertShelfService
from src.domain.services.cel_version_freshness import classify_cel_version_freshness
from src.domain.services.cel_version_pin import parse_document_entity_id
from src.domain.services.document_version_service import document_version_service
from src.domain.services.iso_compliance_service import OPERATIONAL_SIGNAL_TYPES
from src.domain.services.standards_cell_aggregate_service import (
    CLOSED_FINDING_STATUSES,
    OPEN_FINDING_STATUSES,
    detect_recurrence,
    is_nc_finding,
    status_value,
)
from src.domain.services.standards_ingest_gate import STANDARDS_AUTO_CONFIRM_THRESHOLD
from src.domain.services.standards_trap_guard import (
    clause_number_from_token,
    framework_from_clause_token,
)

FINDING_SCAN_LIMIT = 2000
EVIDENCE_SCAN_LIMIT = 2000
PENDING_SCAN_LIMIT = 2000
DIGEST_ROW_LIMIT = 10

AUTO_CONFIRM_RULE = (
    "Machine confirm requires confidence ≥ 0.98, an EXACT alignment row, and a "
    "cell with no open NC or action. This digest reports the queue; it does not "
    "change the gate."
)

SOR_NOTE = (
    "Read-model only — Audits/Findings, Actions, compliance_evidence_links, "
    "the document library, and the certificate shelf remain systems of record."
)


def safe_rate(numerator: int, denominator: int) -> Optional[float]:
    """Return numerator/denominator, or None when the denominator is zero."""
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _clause_path(framework: Optional[str], clause_number: str) -> Optional[str]:
    if not framework or not clause_number:
        return None
    return f"/compliance?code={framework}&clause={clause_number}"


def _dedupe_tokens(tokens: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for token in tokens:
        key = str(token or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(token)
    return out


def _canonical_cell_key(token: Any) -> tuple[Optional[str], str]:
    """Map a stored token to (framework|None, clause_number) for roll-up."""
    framework = framework_from_clause_token(token)
    clause = clause_number_from_token(token)
    if not clause and token is not None:
        clause = str(token).strip()
    return framework, clause


def roll_up_nonconformities(findings: list[dict[str, Any]], *, row_limit: int) -> dict[str, Any]:
    """Roll NC findings into per-clause rows without cross-framework suffix matching."""
    buckets: dict[tuple[Optional[str], str], list[dict[str, Any]]] = defaultdict(list)
    open_finding_ids: set[Any] = set()
    open_without_token = 0
    open_finding_cells: dict[Any, set[tuple[Optional[str], str]]] = defaultdict(set)

    for finding in findings:
        if not is_nc_finding(finding.get("finding_type")):
            continue
        status = status_value(finding.get("status"))
        is_open = status in OPEN_FINDING_STATUSES
        is_closed = status in CLOSED_FINDING_STATUSES
        if not is_open and not is_closed:
            continue

        tokens = _dedupe_tokens(list(finding.get("clause_tokens") or []))
        event = {
            "status": finding.get("status"),
            "created_at": finding.get("created_at"),
            "closed_at": finding.get("updated_at") if is_closed else None,
            "finding_id": finding.get("id"),
        }

        if not tokens:
            if is_open:
                open_without_token += 1
                open_finding_ids.add(finding.get("id"))
            continue

        # Collapse tokens that resolve to the same cell (e.g. "7.5" + "9001-7.5"
        # when framework is declared only on one of them still counts once per
        # distinct (framework, clause) pair within this finding).
        cells_for_finding: set[tuple[Optional[str], str]] = set()
        for token in tokens:
            cell = _canonical_cell_key(token)
            if not cell[1]:
                continue
            cells_for_finding.add(cell)

        if not cells_for_finding:
            if is_open:
                open_without_token += 1
                open_finding_ids.add(finding.get("id"))
            continue

        if is_open:
            open_finding_ids.add(finding.get("id"))

        for cell in cells_for_finding:
            buckets[cell].append(event)
            if is_open:
                open_finding_cells[finding.get("id")].add(cell)

    rows: list[dict[str, Any]] = []
    recurring_clauses = 0
    clauses_with_history = 0
    clauses_with_open = 0
    unattributed_open = 0

    for (framework, clause_number), events in buckets.items():
        open_count = sum(1 for e in events if status_value(e.get("status")) in OPEN_FINDING_STATUSES)
        closed_count = sum(1 for e in events if status_value(e.get("status")) in CLOSED_FINDING_STATUSES)
        recurrence = detect_recurrence(events)
        clauses_with_history += 1
        if recurrence:
            recurring_clauses += 1
        if open_count <= 0:
            continue
        clauses_with_open += 1
        if framework is None:
            unattributed_open += open_count
        latest = max(
            (e.get("created_at") for e in events if e.get("created_at") is not None),
            default=None,
        )
        clause_key = f"{framework}-{clause_number}" if framework else clause_number
        rows.append(
            {
                "framework": framework,
                "clause_number": clause_number,
                "clause_key": clause_key,
                "open_nc_count": open_count,
                "closed_nc_count": closed_count,
                "recurrence": recurrence,
                "latest_nc_at": _iso(latest),
                "clause_path": _clause_path(framework, clause_number),
                "findings_path": "/audits?view=findings",
            }
        )

    rows.sort(
        key=lambda r: (
            -int(r["open_nc_count"]),
            -int(bool(r["recurrence"])),
            str(r.get("framework") or ""),
            str(r.get("clause_number") or ""),
        )
    )

    return {
        "open_nc_total": len(open_finding_ids),
        "open_nc_without_clause_token": open_without_token,
        "clauses_with_open_nc": clauses_with_open,
        "unattributed_open_nc": unattributed_open,
        "recurring_clauses": recurring_clauses,
        "clauses_with_nc_history": clauses_with_history,
        "recurrence_rate": safe_rate(recurring_clauses, clauses_with_history),
        "recurrence_rate_definition": (
            "clauses where an NC reopened after a close ÷ clauses with any NC history"
        ),
        "count_note": (
            "Per-clause counts may exceed the total: one finding can name clauses "
            "in more than one framework."
        ),
        "by_clause": rows[:row_limit],
    }


def roll_up_freshness(
    links: list[dict[str, Any]],
    tips: dict[int, tuple[Optional[int], Optional[str]]],
    *,
    row_limit: int,
    titles: Optional[dict[int, str]] = None,
) -> dict[str, Any]:
    """Classify CEL document pins against library tips."""
    titles = titles or {}
    current = stale = unpinned = unknown = 0
    stale_items: list[dict[str, Any]] = []

    for link in links:
        pinned = link.get("pinned_document_version_id")
        doc_id = link.get("document_id")
        tip_id: Optional[int] = None
        tip_version: Optional[str] = None
        if isinstance(doc_id, int):
            tip_id, tip_version = tips.get(doc_id, (None, None))
        bucket = classify_cel_version_freshness(
            pinned_document_version_id=pinned,
            tip_document_version_id=tip_id,
        )
        if bucket == "current":
            current += 1
        elif bucket == "stale":
            stale += 1
            framework = framework_from_clause_token(link.get("clause_id"))
            clause_number = clause_number_from_token(link.get("clause_id")) or str(
                link.get("clause_id") or ""
            )
            stale_items.append(
                {
                    "evidence_link_id": link.get("id"),
                    "clause_id": link.get("clause_id"),
                    "framework": framework,
                    "clause_number": clause_number,
                    "document_id": doc_id,
                    "title": titles.get(doc_id) if isinstance(doc_id, int) else None,
                    "pinned_document_version_id": pinned,
                    "tip_document_version_id": tip_id,
                    "tip_version_number": tip_version,
                    "clause_path": _clause_path(framework, clause_number),
                    "document_path": f"/documents/{doc_id}" if isinstance(doc_id, int) else None,
                }
            )
        elif bucket == "unpinned":
            unpinned += 1
        else:
            unknown += 1

    resolvable = current + stale
    return {
        "tracked_document_links": len(links),
        "current": current,
        "stale": stale,
        "unpinned": unpinned,
        "unknown": unknown,
        "stale_rate": safe_rate(stale, resolvable),
        "stale_rate_definition": "stale pins ÷ pins with a resolvable tip (current + stale)",
        "stale_items": stale_items[:row_limit],
    }


def roll_up_ingest_backlog(
    links: list[dict[str, Any]],
    *,
    now: datetime,
    row_limit: int,
) -> dict[str, Any]:
    """Pending evidence inbox roll-up (proposed / needs_review via effective_status)."""
    by_status: dict[str, int] = defaultdict(int)
    by_method: dict[str, int] = defaultdict(int)
    by_clause: dict[str, dict[str, Any]] = {}
    operational = 0
    conformance = 0
    oldest: Optional[datetime] = None

    for link in links:
        status = str(link.get("effective_status") or "").strip().lower()
        by_status[status or "proposed"] += 1
        method = str(link.get("linked_by") or "unknown").strip().lower()
        by_method[method] += 1
        signal = str(link.get("signal_type") or "").strip().lower()
        if signal in OPERATIONAL_SIGNAL_TYPES:
            operational += 1
        else:
            conformance += 1

        created = link.get("created_at")
        if isinstance(created, datetime):
            created_cmp = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
            now_cmp = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
            if oldest is None or created_cmp < oldest:
                oldest = created_cmp

        clause_id = str(link.get("clause_id") or "").strip()
        if not clause_id:
            continue
        bucket = by_clause.setdefault(
            clause_id,
            {
                "clause_id": clause_id,
                "framework": framework_from_clause_token(clause_id),
                "clause_number": clause_number_from_token(clause_id) or clause_id,
                "count": 0,
                "inbox_path": f"/knowledge-exceptions?clause={clause_id}",
            },
        )
        bucket["count"] += 1

    clause_rows = sorted(by_clause.values(), key=lambda r: (-int(r["count"]), str(r["clause_id"])))
    oldest_age_days: Optional[int] = None
    if oldest is not None:
        now_cmp = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        oldest_age_days = max(0, (now_cmp - oldest).days)

    return {
        "total": len(links),
        "by_status": dict(by_status),
        "by_link_method": dict(by_method),
        "operational_signals": operational,
        "conformance_candidates": conformance,
        "oldest_created_at": _iso(oldest),
        "oldest_age_days": oldest_age_days,
        "by_clause": clause_rows[:row_limit],
        "auto_confirm_threshold": STANDARDS_AUTO_CONFIRM_THRESHOLD,
        "auto_confirm_rule": AUTO_CONFIRM_RULE,
        "inbox_path": "/knowledge-exceptions",
    }


def roll_up_cert_expiry(
    shelf: dict[str, Any],
    *,
    now: datetime,
    row_limit: int,
) -> dict[str, Any]:
    """Board view over the unified assurance certificate shelf."""
    summary = dict(shelf.get("summary") or {})
    items = list(shelf.get("items") or [])
    by_scheme_map: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tracked": 0, "due_soon": 0, "expired": 0}
    )
    soonest: list[dict[str, Any]] = []

    today = now.date() if isinstance(now, datetime) else date.today()
    for item in items:
        scheme = str(item.get("scheme") or "unknown")
        readiness = str(item.get("readiness_status") or "unknown")
        by_scheme_map[scheme]["tracked"] += 1
        if readiness == "due_soon":
            by_scheme_map[scheme]["due_soon"] += 1
        elif readiness == "expired":
            by_scheme_map[scheme]["expired"] += 1

        if readiness not in {"due_soon", "expired"}:
            continue
        expiry_raw = item.get("expiry_date")
        expiry_date: Optional[date] = None
        if isinstance(expiry_raw, date) and not isinstance(expiry_raw, datetime):
            expiry_date = expiry_raw
        elif isinstance(expiry_raw, datetime):
            expiry_date = expiry_raw.date()
        elif isinstance(expiry_raw, str) and expiry_raw:
            try:
                expiry_date = date.fromisoformat(expiry_raw[:10])
            except ValueError:
                expiry_date = None
        days_remaining = (expiry_date - today).days if expiry_date else None
        soonest.append(
            {
                "shelf_key": item.get("shelf_key"),
                "name": item.get("name"),
                "scheme": scheme,
                "expiry_date": expiry_date.isoformat() if expiry_date else expiry_raw,
                "readiness_status": readiness,
                "days_remaining": days_remaining,
                "is_critical": bool(item.get("is_critical")),
                "detail_path": "/compliance-schedule?view=certificates",
            }
        )

    soonest.sort(
        key=lambda row: (
            row["days_remaining"] is None,
            row["days_remaining"] if row["days_remaining"] is not None else 10**9,
            str(row.get("name") or ""),
        )
    )
    by_scheme = [
        {"scheme": scheme, **counts}
        for scheme, counts in sorted(by_scheme_map.items(), key=lambda kv: (-kv[1]["tracked"], kv[0]))
    ]

    return {
        "tracked": int(summary.get("tracked") or summary.get("total") or len(items)),
        "valid": int(summary.get("valid") or 0),
        "due_soon": int(summary.get("due_soon") or 0),
        "expired": int(summary.get("expired") or 0),
        "unknown": int(summary.get("unknown") or 0),
        "by_scheme": by_scheme,
        "soonest": soonest[:row_limit],
        "shelf_path": "/compliance-schedule?view=certificates",
    }


class StandardsDigestService:
    """Compose Standards Monitoring digests for one tenant."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.cert_shelf = AssuranceCertShelfService(db)

    async def build(
        self,
        *,
        tenant_id: int,
        due_soon_days: int = 30,
        now: Optional[datetime] = None,
    ) -> dict[str, Any]:
        reference = now or datetime.now(timezone.utc)

        findings, findings_truncated = await self._load_findings(tenant_id)
        doc_links, evidence_truncated = await self._load_document_links(tenant_id)
        pending_links, pending_truncated = await self._load_pending_links(tenant_id)

        doc_ids = sorted({link["document_id"] for link in doc_links if isinstance(link.get("document_id"), int)})
        tips = await document_version_service.resolve_tip_library_version_ids(
            self.db, document_ids=doc_ids, tenant_id=tenant_id
        )
        titles = await self._load_document_titles(doc_ids, tenant_id=tenant_id)

        shelf = await self.cert_shelf.get_shelf(
            tenant_id=tenant_id, due_soon_days=due_soon_days, now=reference
        )

        nc = roll_up_nonconformities(findings, row_limit=DIGEST_ROW_LIMIT)
        nc["scan_truncated"] = findings_truncated

        freshness = roll_up_freshness(doc_links, tips, row_limit=DIGEST_ROW_LIMIT, titles=titles)
        freshness["scan_truncated"] = evidence_truncated

        backlog = roll_up_ingest_backlog(pending_links, now=reference, row_limit=DIGEST_ROW_LIMIT)
        backlog["scan_truncated"] = pending_truncated

        certs = roll_up_cert_expiry(shelf, now=reference, row_limit=DIGEST_ROW_LIMIT)

        return {
            "generated_at": reference.isoformat(),
            "due_soon_days": due_soon_days,
            "freshness": freshness,
            "ingest_backlog": backlog,
            "nonconformity": nc,
            "cert_expiry": certs,
            "sor_note": SOR_NOTE,
            "limits": {
                "finding_scan": FINDING_SCAN_LIMIT,
                "evidence_scan": EVIDENCE_SCAN_LIMIT,
                "pending_scan": PENDING_SCAN_LIMIT,
                "rows": DIGEST_ROW_LIMIT,
            },
        }

    async def _load_findings(self, tenant_id: int) -> tuple[list[dict[str, Any]], bool]:
        result = await self.db.execute(
            select(AuditFinding)
            .where(AuditFinding.tenant_id == tenant_id)
            .order_by(AuditFinding.created_at.desc())
            .limit(FINDING_SCAN_LIMIT)
        )
        rows = list(result.scalars().all())
        truncated = len(rows) >= FINDING_SCAN_LIMIT
        payload = [
            {
                "id": finding.id,
                "finding_type": finding.finding_type,
                "status": finding.status,
                "created_at": finding.created_at,
                "updated_at": finding.updated_at,
                "clause_tokens": list(finding.clause_ids_json_legacy or []),
            }
            for finding in rows
        ]
        return payload, truncated

    async def _load_document_links(self, tenant_id: int) -> tuple[list[dict[str, Any]], bool]:
        result = await self.db.execute(
            select(ComplianceEvidenceLink)
            .where(
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.deleted_at.is_(None),
                ComplianceEvidenceLink.entity_type == "document",
            )
            .order_by(ComplianceEvidenceLink.created_at.desc())
            .limit(EVIDENCE_SCAN_LIMIT)
        )
        rows = list(result.scalars().all())
        truncated = len(rows) >= EVIDENCE_SCAN_LIMIT
        payload = []
        for link in rows:
            payload.append(
                {
                    "id": link.id,
                    "clause_id": link.clause_id,
                    "pinned_document_version_id": link.document_version_id,
                    "document_id": parse_document_entity_id(link.entity_id),
                }
            )
        return payload, truncated

    async def _load_pending_links(self, tenant_id: int) -> tuple[list[dict[str, Any]], bool]:
        statuses = [EvidenceLinkStatus.PROPOSED, EvidenceLinkStatus.NEEDS_REVIEW]
        result = await self.db.execute(
            select(ComplianceEvidenceLink)
            .where(
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.deleted_at.is_(None),
                or_(
                    ComplianceEvidenceLink.status.in_(statuses),
                    ComplianceEvidenceLink.status.is_(None),
                ),
            )
            .order_by(ComplianceEvidenceLink.created_at.desc())
            .limit(PENDING_SCAN_LIMIT)
        )
        rows = [
            link
            for link in result.scalars().all()
            if link.effective_status in statuses
        ]
        # Truncation is approximate when SQL returns the cap then Python filters.
        truncated = len(rows) >= PENDING_SCAN_LIMIT
        payload = []
        for link in rows:
            linked_by = link.linked_by
            if hasattr(linked_by, "value"):
                linked_by = linked_by.value
            payload.append(
                {
                    "id": link.id,
                    "clause_id": link.clause_id,
                    "effective_status": link.effective_status.value,
                    "linked_by": linked_by or EvidenceLinkMethod.AI.value,
                    "signal_type": link.signal_type,
                    "created_at": link.created_at,
                }
            )
        return payload, truncated

    async def _load_document_titles(
        self, document_ids: list[int], *, tenant_id: int
    ) -> dict[int, str]:
        if not document_ids:
            return {}
        result = await self.db.execute(
            select(Document.id, Document.title).where(
                Document.tenant_id == tenant_id,
                Document.id.in_(document_ids),
            )
        )
        return {int(row.id): str(row.title or "") for row in result.all()}
