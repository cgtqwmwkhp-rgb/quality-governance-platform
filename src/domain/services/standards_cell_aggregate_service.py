"""Standards cell aggregate read-model (Wave 1 PR-B).

Joins existing SoR modules — audits/findings, capa_actions, risks,
AssuranceCertShelf, external audit records, and compliance evidence links —
into a per-cell verdict + workspace payload. Does **not** invent a second
Standards database (LIVE-08).

Wave 2 PR-C annotates this aggregate rather than replacing it. Two guards run
over the matches this module makes:

``TrapGuard``
    The clause-token matching below is deliberately tolerant, including a
    framework-blind suffix rule, so a link written against ``14001-9.1.2``
    (evaluation of compliance) also matches the ISO 9001 9.1.2 cell (customer
    satisfaction). The guard drops those matches where the imported alignment
    matrix says the two clauses share a number and nothing else.

``TechGapGuard``
    A technical control cannot be closed by a document. Where a cell is one of the
    technical requirements PEL-HSEQ-5064 names, a document-only cover is refused
    the ``covered`` verdict.

Both guards are additive: with no matrix imported they have no opinion, and the
verdict computation is unchanged from PR-B.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.models.audit import AuditFinding, AuditRun, AuditTemplate, FindingStatus
from src.domain.models.capa import CAPAAction, CAPAStatus
from src.domain.models.compliance_evidence import ComplianceEvidenceLink
from src.domain.models.external_audit_record import ExternalAuditRecord
from src.domain.models.risk import Risk
from src.domain.models.risk_register import EnterpriseRisk, EnterpriseRiskControl
from src.domain.services.assurance_cert_shelf_service import AssuranceCertShelfService
from src.domain.services.iso_compliance_service import (
    OPERATIONAL_SIGNAL_TYPES,
    counts_toward_compliance_coverage,
    iso_compliance_service,
)
from src.domain.services import standards_tech_gap_guard as tech_gap_guard
from src.domain.services.standards_trap_guard import TrapGuard

OPEN_FINDING_STATUSES = frozenset(
    {
        FindingStatus.OPEN.value,
        FindingStatus.IN_PROGRESS.value,
        FindingStatus.PENDING_VERIFICATION.value,
        FindingStatus.DEFERRED.value,
        "open",
        "in_progress",
        "pending_verification",
        "deferred",
    }
)
CLOSED_FINDING_STATUSES = frozenset({FindingStatus.CLOSED.value, "closed"})

OPEN_ACTION_STATUSES = frozenset(
    {
        CAPAStatus.OPEN.value,
        CAPAStatus.IN_PROGRESS.value,
        CAPAStatus.VERIFICATION.value,
        CAPAStatus.OVERDUE.value,
        "open",
        "in_progress",
        "verification",
        "overdue",
    }
)

NC_FINDING_TYPES = frozenset(
    {
        "nonconformity",
        "major_nonconformity",
        "minor_nonconformity",
        "ncr",
        "nc",
        "competence_gap",
        "finding",
        "flagged_item",
        "question_answered_no",
    }
)

# Matrix framework id → ISO catalogue / cert scheme aliases
FRAMEWORK_ALIASES: dict[str, dict[str, Any]] = {
    "9001": {
        "iso": "iso9001",
        "prefix": "9001",
        "cert_schemes": ("iso9001", "iso", "iso_9001", "9001", "register"),
        "record_schemes": ("iso", "iso9001"),
    },
    "14001": {
        "iso": "iso14001",
        "prefix": "14001",
        "cert_schemes": ("iso14001", "iso", "iso_14001", "14001", "register"),
        "record_schemes": ("iso", "iso14001"),
    },
    "45001": {
        "iso": "iso45001",
        "prefix": "45001",
        "cert_schemes": ("iso45001", "iso", "iso_45001", "45001", "register"),
        "record_schemes": ("iso", "iso45001"),
    },
    "27001": {
        "iso": "iso27001",
        "prefix": "27001",
        "cert_schemes": ("iso27001", "iso", "iso_27001", "27001", "register"),
        "record_schemes": ("iso", "iso27001"),
    },
    "22301": {
        "iso": None,
        "prefix": "22301",
        "cert_schemes": ("iso22301", "iso", "22301", "register"),
        "record_schemes": ("iso", "iso22301"),
    },
    "uvdb": {
        "iso": None,
        "prefix": "uvdb",
        "cert_schemes": ("uvdb", "achilles", "achilles_uvdb"),
        "record_schemes": ("uvdb", "achilles_uvdb", "achilles"),
    },
    "pm": {
        "iso": None,
        "prefix": "pm",
        "cert_schemes": ("planet_mark", "pm"),
        "record_schemes": ("planet_mark",),
    },
    "ce": {
        "iso": None,
        "prefix": "ce",
        "cert_schemes": ("carbon_evolve", "ce", "register"),
        "record_schemes": ("carbon_evolve", "ce"),
    },
    "cep": {
        "iso": None,
        "prefix": "cep",
        "cert_schemes": ("carbon_evolve_plus", "cep", "register"),
        "record_schemes": ("carbon_evolve_plus", "cep"),
    },
    "iip": {
        "iso": None,
        "prefix": "iip",
        "cert_schemes": ("iip", "investors_in_people", "register"),
        "record_schemes": ("iip",),
    },
    "chas": {
        "iso": None,
        "prefix": "chas",
        "cert_schemes": ("chas", "register"),
        "record_schemes": ("chas",),
    },
    "ssip": {
        "iso": None,
        "prefix": "ssip",
        "cert_schemes": ("ssip", "register"),
        "record_schemes": ("ssip",),
    },
}


def normalize_clause_token(value: Any) -> str:
    """Normalize clause tokens for tolerant matching (4.1, 9001-4.1, Clause 4.1)."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    text = text.replace("clause", " ").replace("cl.", " ")
    text = text.replace("_", "-").replace(" ", "")
    return text


def clause_match_keys(framework: str, clause_number: str) -> set[str]:
    """Candidate keys a finding/action/CEL may use for this matrix cell."""
    fw = (framework or "").strip().lower()
    clause = (clause_number or "").strip()
    if not clause:
        return set()
    keys = {
        normalize_clause_token(clause),
        normalize_clause_token(f"{fw}-{clause}"),
        normalize_clause_token(f"{fw}:{clause}"),
    }
    alias = FRAMEWORK_ALIASES.get(fw, {})
    prefix = alias.get("prefix")
    iso = alias.get("iso")
    if prefix:
        keys.add(normalize_clause_token(f"{prefix}-{clause}"))
    if iso:
        keys.add(normalize_clause_token(f"{iso}-{clause}"))
        # Catalogue ids look like 9001-4.1 (prefix without "iso")
        numeric = str(iso).replace("iso", "")
        keys.add(normalize_clause_token(f"{numeric}-{clause}"))
    return {k for k in keys if k}


def token_matches_clause(token: Any, keys: set[str], clause_number: str) -> bool:
    """True when a stored clause token refers to this cell."""
    norm = normalize_clause_token(token)
    if not norm:
        return False
    if norm in keys:
        return True
    clause_norm = normalize_clause_token(clause_number)
    if not clause_norm:
        return False
    # Suffix match: "9001-7.5" / "iso9001:7.5" against clause "7.5"
    if norm.endswith(f"-{clause_norm}") or norm.endswith(f":{clause_norm}"):
        return True
    # Bare clause number equality already covered via keys; also allow startswith for sub-clauses
    if norm == clause_norm or norm.startswith(f"{clause_norm}."):
        return True
    return False


def any_token_matches(tokens: Optional[Iterable[Any]], keys: set[str], clause_number: str) -> bool:
    if not tokens:
        return False
    for token in tokens:
        if token_matches_clause(token, keys, clause_number):
            return True
    return False


def status_value(status: Any) -> str:
    if status is None:
        return ""
    if hasattr(status, "value"):
        return str(status.value).strip().lower()
    return str(status).strip().lower()


def is_nc_finding(finding_type: Optional[str]) -> bool:
    if not finding_type:
        return True  # default finding_type on model is nonconformity-ish; treat unknown as NC signal
    return finding_type.strip().lower() in NC_FINDING_TYPES


def classify_audit_kind(
    *,
    assessment_mode: Optional[str],
    source_origin: Optional[str],
    template_tags: Optional[list],
    is_external_import: bool = False,
) -> str:
    """Return mock | imported | internal — honest labels for workspace."""
    if is_external_import:
        return "imported"
    origin = (source_origin or "").strip().lower()
    if origin in {"external_import", "external_audit", "uvdb_import", "imported"} or "import" in origin:
        return "imported"
    mode = (assessment_mode or "").strip().lower()
    if mode == "mock" or origin == "mock":
        return "mock"
    tags = template_tags or []
    for tag in tags:
        if isinstance(tag, str) and tag.strip().lower() == "mock":
            return "mock"
    return "internal"


def detect_recurrence(nc_events: list[dict[str, Any]]) -> bool:
    """True when an NC appears again after a prior close on the same clause."""
    if len(nc_events) < 2:
        return False
    ordered = sorted(
        nc_events,
        key=lambda e: e.get("closed_at") or e.get("created_at") or datetime.min,
    )
    saw_closed = False
    for event in ordered:
        status = status_value(event.get("status"))
        if status in CLOSED_FINDING_STATUSES:
            saw_closed = True
            continue
        if saw_closed and status in OPEN_FINDING_STATUSES:
            return True
    return False


def compute_cell_verdict(
    *,
    open_nc_count: int,
    open_action_count: int,
    recurrence: bool,
    conformance_evidence_count: int,
    mock_gap_count: int,
    closed_nc_count: int,
) -> dict[str, Any]:
    """Cover gate: open NC / open action → never covered. Mock gaps stay honest."""
    cover_blocked = open_nc_count > 0 or open_action_count > 0
    reasons: list[str] = []

    if open_nc_count > 0:
        reasons.append("open_nc")
    if open_action_count > 0:
        reasons.append("open_action")
    if recurrence:
        reasons.append("recurrence")
    if mock_gap_count > 0:
        reasons.append("mock_gap")

    if open_nc_count > 0:
        verdict = "gap"
    elif open_action_count > 0:
        verdict = "partial"
    elif recurrence and conformance_evidence_count == 0:
        verdict = "gap"
    elif conformance_evidence_count > 0 and not cover_blocked:
        verdict = "covered" if closed_nc_count == 0 and not recurrence else "partial"
    elif mock_gap_count > 0 or closed_nc_count > 0:
        verdict = "gap" if mock_gap_count > 0 and conformance_evidence_count == 0 else "partial"
    else:
        verdict = "unknown"

    # Hard rule: open NC/action must never report covered
    if cover_blocked and verdict == "covered":
        verdict = "partial" if open_nc_count == 0 else "gap"

    return {
        "verdict": verdict,
        "cover_blocked": cover_blocked,
        "recurrence_red_flag": recurrence,
        "reasons": reasons,
    }


@dataclass
class CellAggregateResult:
    framework: str
    clause_number: str
    catalogue_keys: list[str]
    verdict: str
    cover_blocked: bool
    recurrence_red_flag: bool
    reasons: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    risks: list[dict[str, Any]] = field(default_factory=list)
    certificates: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    imported_priors: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    #: PR-C: imported alignment context for this cell (row verdict, peers, traps).
    alignment: dict[str, Any] = field(default_factory=dict)
    #: PR-C: matches TrapGuard refused because the clause number is shared but the
    #: requirement is not. Surfaced rather than dropped silently.
    trap_blocked: list[dict[str, Any]] = field(default_factory=list)
    #: PR-C: TechGapGuard verdict where this cell is a technical control.
    tech_gap: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework": self.framework,
            "clause_number": self.clause_number,
            "catalogue_keys": self.catalogue_keys,
            "verdict": self.verdict,
            "cover_blocked": self.cover_blocked,
            "recurrence_red_flag": self.recurrence_red_flag,
            "reasons": self.reasons,
            "findings": self.findings,
            "actions": self.actions,
            "risks": self.risks,
            "certificates": self.certificates,
            "evidence": self.evidence,
            "imported_priors": self.imported_priors,
            "summary": self.summary,
            "alignment": self.alignment,
            "trap_blocked": self.trap_blocked,
            "tech_gap": self.tech_gap,
            "sor_note": "Audits, Actions, Risk Register, Cert Shelf, and External Audit Records remain SoR — this is a read-model join only.",
        }


class StandardsCellAggregateService:
    """Read-model join for Standards matrix cells / Evidence Workspace panels."""

    def __init__(self, db: AsyncSession, *, trap_guard: Optional[TrapGuard] = None):
        self.db = db
        self.cert_shelf = AssuranceCertShelfService(db)
        # Loaded once per service instance on first use: a matrix batch asks for up
        # to 200 cells and must not re-read the alignment edition 200 times.
        self._trap_guard = trap_guard

    async def trap_guard(self, tenant_id: int) -> TrapGuard:
        """The tenant's alignment snapshot, loaded once per service instance."""
        if self._trap_guard is None:
            self._trap_guard = await TrapGuard.for_tenant(self.db, tenant_id)
        return self._trap_guard

    def catalogue_keys_for(self, framework: str, clause_number: str) -> list[str]:
        keys = sorted(clause_match_keys(framework, clause_number))
        alias = FRAMEWORK_ALIASES.get(framework.strip().lower(), {})
        iso = alias.get("iso")
        if iso:
            # Prefer canonical ALL_CLAUSES id when present
            for clause in iso_compliance_service.get_all_clauses():
                if clause.standard.value == iso and clause.clause_number == clause_number:
                    if clause.id not in keys:
                        keys.insert(0, normalize_clause_token(clause.id))
                    break
        return keys

    async def get_cell(self, *, tenant_id: int, framework: str, clause_number: str) -> CellAggregateResult:
        fw = framework.strip().lower()
        clause = clause_number.strip()
        keys = clause_match_keys(fw, clause)
        catalogue_keys = self.catalogue_keys_for(fw, clause)

        guard = await self.trap_guard(tenant_id)
        trap_blocked: list[dict[str, Any]] = []

        findings = await self._findings_for_cell(
            tenant_id=tenant_id, keys=keys, clause_number=clause, guard=guard, framework=fw, blocked=trap_blocked
        )
        actions = await self._actions_for_cell(
            tenant_id=tenant_id, keys=keys, clause_number=clause, guard=guard, framework=fw, blocked=trap_blocked
        )
        evidence = await self._evidence_for_cell(
            tenant_id=tenant_id, keys=keys, clause_number=clause, guard=guard, framework=fw, blocked=trap_blocked
        )
        risks = await self._risks_for_cell(
            tenant_id=tenant_id,
            keys=keys,
            clause_number=clause,
            finding_ids=[f["id"] for f in findings],
        )
        certificates = await self._certs_for_framework(tenant_id=tenant_id, framework=fw, clause_number=clause)
        imported = await self._imported_priors(
            tenant_id=tenant_id, framework=fw, finding_run_ids={f["run_id"] for f in findings}
        )

        open_ncs = [f for f in findings if f.get("is_nc") and status_value(f.get("status")) in OPEN_FINDING_STATUSES]
        closed_ncs = [
            f for f in findings if f.get("is_nc") and status_value(f.get("status")) in CLOSED_FINDING_STATUSES
        ]
        open_actions = [a for a in actions if status_value(a.get("status")) in OPEN_ACTION_STATUSES]
        mock_gaps = [
            f
            for f in findings
            if f.get("audit_kind") == "mock"
            and f.get("is_nc")
            and status_value(f.get("status")) in OPEN_FINDING_STATUSES
        ]
        conformance = [e for e in evidence if counts_toward_compliance_coverage(e.get("signal_type"))]

        nc_events = [
            {
                "status": f.get("status"),
                "created_at": f.get("created_at"),
                "closed_at": f.get("updated_at") if status_value(f.get("status")) in CLOSED_FINDING_STATUSES else None,
            }
            for f in findings
            if f.get("is_nc")
        ]
        recurrence = detect_recurrence(nc_events)
        verdict_info = compute_cell_verdict(
            open_nc_count=len(open_ncs),
            open_action_count=len(open_actions),
            recurrence=recurrence,
            conformance_evidence_count=len(conformance),
            mock_gap_count=len(mock_gaps),
            closed_nc_count=len(closed_ncs),
        )

        # PR-C TechGapGuard: a technical control cannot be closed by a document.
        # Applied after the PR-B verdict so it can only ever tighten it.
        tech_gap = tech_gap_guard.assess(
            framework=fw,
            clause_number=clause,
            entity_types=[e.get("entity_type") for e in conformance if e.get("entity_type")],
        )
        if tech_gap.is_technical and not tech_gap.covered and verdict_info["verdict"] == "covered":
            verdict_info["verdict"] = "partial"
            verdict_info["reasons"] = [*verdict_info["reasons"], "tech_gap_attestation_missing"]

        top_evidence = None
        if conformance:
            top_evidence = conformance[0].get("title") or conformance[0].get("entity_type")
        elif findings:
            top_evidence = findings[0].get("title")

        freshness = None
        timestamps = [
            v
            for v in (
                *[f.get("updated_at") or f.get("created_at") for f in findings],
                *[a.get("updated_at") or a.get("created_at") for a in actions],
                *[e.get("updated_at") or e.get("created_at") for e in evidence],
            )
            if v
        ]
        if timestamps:
            freshness = max(timestamps)

        return CellAggregateResult(
            framework=fw,
            clause_number=clause,
            catalogue_keys=catalogue_keys,
            verdict=verdict_info["verdict"],
            cover_blocked=verdict_info["cover_blocked"],
            recurrence_red_flag=verdict_info["recurrence_red_flag"],
            reasons=verdict_info["reasons"],
            findings=findings,
            actions=actions,
            risks=risks,
            certificates=certificates,
            evidence=evidence,
            imported_priors=imported,
            summary={
                "open_nc_count": len(open_ncs),
                "closed_nc_count": len(closed_ncs),
                "open_action_count": len(open_actions),
                "risk_count": len(risks),
                "cert_count": len(certificates),
                "evidence_count": len(conformance),
                "imported_prior_count": len(imported),
                "mock_finding_count": sum(1 for f in findings if f.get("audit_kind") == "mock"),
                "top_evidence_label": top_evidence,
                "freshness": freshness,
                "trap_blocked_count": len(trap_blocked),
            },
            alignment=guard.annotate_cell(framework=fw, clause_number=clause),
            trap_blocked=trap_blocked,
            tech_gap=tech_gap.to_dict() if tech_gap.is_technical else {},
        )

    async def get_matrix_summary(
        self,
        *,
        tenant_id: int,
        frameworks: list[str],
        clause_numbers: list[str],
    ) -> dict[str, Any]:
        """Batch verdicts for matrix paint — same cover gate as get_cell."""
        # Load the alignment edition once for the whole batch rather than per cell.
        guard = await self.trap_guard(tenant_id)
        cells: list[dict[str, Any]] = []
        for fw in frameworks:
            for clause in clause_numbers:
                cell = await self.get_cell(tenant_id=tenant_id, framework=fw, clause_number=clause)
                cells.append(
                    {
                        "framework": cell.framework,
                        "clause_number": cell.clause_number,
                        "verdict": cell.verdict,
                        "cover_blocked": cell.cover_blocked,
                        "recurrence_red_flag": cell.recurrence_red_flag,
                        "reasons": cell.reasons,
                        "summary": cell.summary,
                        "alignment": cell.alignment,
                        "tech_gap": cell.tech_gap,
                    }
                )
        return {
            "cells": cells,
            "matrix_version": guard.version_label,
            "matrix_loaded": guard.is_loaded,
            "sor_note": "Read-model only — Audits/Actions/Risk/Cert shelf remain SoR.",
        }

    def _survives_trap_guard(
        self,
        *,
        guard: TrapGuard,
        framework: str,
        clause_number: str,
        tokens: list[Any],
        keys: set[str],
        blocked: list[dict[str, Any]],
        source: str,
        record: dict[str, Any],
    ) -> bool:
        """True when a match still holds after cross-framework traps are removed.

        Only tokens naming a *different* framework can be removed, and only where
        the matrix carries a DIFFERENT or UNIQUE verdict for the pair. If every
        token that produced the match is removed, the match itself goes — the
        record matched this cell on a clause number it does not share.
        """
        if not guard.is_loaded:
            return True
        kept, refused = guard.filter_cross_framework_tokens(
            framework=framework,
            clause_number=clause_number,
            tokens=tokens,
        )
        if not refused:
            return True
        if any_token_matches(kept, keys, clause_number):
            return True
        for entry in refused:
            blocked.append({**entry, "source": source, **record})
        return False

    async def _findings_for_cell(
        self,
        *,
        tenant_id: int,
        keys: set[str],
        clause_number: str,
        guard: TrapGuard,
        framework: str,
        blocked: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        query = (
            select(AuditFinding)
            .options(
                selectinload(AuditFinding.run).selectinload(AuditRun.template),
                selectinload(AuditFinding.risks),
            )
            .where(AuditFinding.tenant_id == tenant_id)
            .order_by(AuditFinding.created_at.desc())
            .limit(500)
        )
        rows = (await self.db.execute(query)).scalars().all()
        matched: list[dict[str, Any]] = []
        for finding in rows:
            tokens = list(finding.clause_ids_json_legacy or [])
            if not any_token_matches(tokens, keys, clause_number):
                continue
            if not self._survives_trap_guard(
                guard=guard,
                framework=framework,
                clause_number=clause_number,
                tokens=tokens,
                keys=keys,
                blocked=blocked,
                source="finding",
                record={"record_id": finding.id, "record_title": finding.title},
            ):
                continue
            run = finding.run
            template = run.template if run else None
            is_external = bool(
                run
                and (
                    "import" in (run.source_origin or "").lower()
                    or (template is not None and template.audit_type == "external_import")
                )
            )
            kind = classify_audit_kind(
                assessment_mode=run.assessment_mode if run else None,
                source_origin=run.source_origin if run else None,
                template_tags=list(template.tags_json or []) if template else None,
                is_external_import=is_external,
            )
            matched.append(
                {
                    "id": finding.id,
                    "reference_number": finding.reference_number,
                    "run_id": finding.run_id,
                    "title": finding.title,
                    "description": finding.description,
                    "severity": finding.severity,
                    "finding_type": finding.finding_type,
                    "status": status_value(finding.status),
                    "is_nc": is_nc_finding(finding.finding_type),
                    "audit_kind": kind,
                    "clause_ids": tokens,
                    "risk_ids": finding.risk_ids_json,
                    "created_at": finding.created_at.isoformat() if finding.created_at else None,
                    "updated_at": finding.updated_at.isoformat() if finding.updated_at else None,
                    "detail_path": f"/audits?view=findings&findingId={finding.id}",
                }
            )
        return matched

    async def _actions_for_cell(
        self,
        *,
        tenant_id: int,
        keys: set[str],
        clause_number: str,
        guard: TrapGuard,
        framework: str,
        blocked: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        query = (
            select(CAPAAction)
            .where(CAPAAction.tenant_id == tenant_id)
            .order_by(CAPAAction.created_at.desc())
            .limit(500)
        )
        rows = (await self.db.execute(query)).scalars().all()
        matched: list[dict[str, Any]] = []
        for action in rows:
            ref = action.clause_reference
            iso = action.iso_standard
            tokens: list[str] = []
            if ref:
                # clause_reference may be "7.5" or "7.5, 8.1"
                tokens.extend(part.strip() for part in str(ref).replace(";", ",").split(",") if part.strip())
            if iso and ref:
                tokens.append(f"{iso}-{ref}")
            if not any_token_matches(tokens, keys, clause_number):
                continue
            if not self._survives_trap_guard(
                guard=guard,
                framework=framework,
                clause_number=clause_number,
                tokens=tokens,
                keys=keys,
                blocked=blocked,
                source="action",
                record={"record_id": action.id, "record_title": action.title},
            ):
                continue
            matched.append(
                {
                    "id": action.id,
                    "reference_number": action.reference_number,
                    "title": action.title,
                    "status": status_value(action.status),
                    "priority": status_value(action.priority) if action.priority else None,
                    "source_type": status_value(action.source_type) if action.source_type else None,
                    "source_id": action.source_id,
                    "clause_reference": action.clause_reference,
                    "iso_standard": action.iso_standard,
                    "due_date": action.due_date.isoformat() if action.due_date else None,
                    "created_at": action.created_at.isoformat() if action.created_at else None,
                    "updated_at": action.updated_at.isoformat() if action.updated_at else None,
                    "detail_path": f"/actions/{action.id}",
                }
            )
        return matched

    async def _evidence_for_cell(
        self,
        *,
        tenant_id: int,
        keys: set[str],
        clause_number: str,
        guard: TrapGuard,
        framework: str,
        blocked: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        query = (
            select(ComplianceEvidenceLink)
            .where(
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.deleted_at.is_(None),
            )
            .order_by(ComplianceEvidenceLink.created_at.desc())
            .limit(500)
        )
        rows = (await self.db.execute(query)).scalars().all()
        matched: list[dict[str, Any]] = []
        for link in rows:
            if not token_matches_clause(link.clause_id, keys, clause_number):
                continue
            if not self._survives_trap_guard(
                guard=guard,
                framework=framework,
                clause_number=clause_number,
                tokens=[link.clause_id],
                keys=keys,
                blocked=blocked,
                source="evidence_link",
                record={"record_id": link.id, "record_title": link.title},
            ):
                continue
            signal = link.signal_type or None
            matched.append(
                {
                    "id": link.id,
                    "entity_type": link.entity_type,
                    "entity_id": link.entity_id,
                    "clause_id": link.clause_id,
                    "title": link.title,
                    "signal_type": signal,
                    "is_operational_signal": (signal or "").lower() in OPERATIONAL_SIGNAL_TYPES,
                    "status": status_value(link.status) if link.status else None,
                    "created_at": link.created_at.isoformat() if link.created_at else None,
                    "updated_at": link.updated_at.isoformat() if link.updated_at else None,
                }
            )
        return matched

    async def _risks_for_cell(
        self,
        *,
        tenant_id: int,
        keys: set[str],
        clause_number: str,
        finding_ids: list[int],
    ) -> list[dict[str, Any]]:
        matched: dict[str, dict[str, Any]] = {}

        # Operational risks with legacy clause ids
        risk_rows = (await self.db.execute(select(Risk).where(Risk.tenant_id == tenant_id).limit(500))).scalars().all()
        for risk in risk_rows:
            if not any_token_matches(risk.clause_ids_json_legacy, keys, clause_number):
                continue
            key = f"op-{risk.id}"
            matched[key] = {
                "id": risk.id,
                "register": "operational",
                "reference": risk.reference_number,
                "title": risk.title,
                "status": status_value(risk.status),
                "detail_path": f"/risks/{risk.id}",
                "source": "clause_ids",
            }

        # Enterprise controls with standard_clauses
        control_rows = (
            (
                await self.db.execute(
                    select(EnterpriseRiskControl).where(EnterpriseRiskControl.tenant_id == tenant_id).limit(500)
                )
            )
            .scalars()
            .all()
        )
        control_ids = [c.id for c in control_rows if any_token_matches(c.standard_clauses, keys, clause_number)]
        if control_ids:
            from src.domain.models.risk_register import RiskControlMapping

            maps = (
                (
                    await self.db.execute(
                        select(RiskControlMapping).where(
                            RiskControlMapping.tenant_id == tenant_id,
                            RiskControlMapping.control_id.in_(control_ids),
                        )
                    )
                )
                .scalars()
                .all()
            )
            risk_ids = {m.risk_id for m in maps}
            if risk_ids:
                er_rows = (
                    (
                        await self.db.execute(
                            select(EnterpriseRisk).where(
                                EnterpriseRisk.tenant_id == tenant_id,
                                EnterpriseRisk.id.in_(risk_ids),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                for er_risk in er_rows:
                    key = f"er-{er_risk.id}"
                    matched[key] = {
                        "id": er_risk.id,
                        "register": "enterprise",
                        "reference": er_risk.reference,
                        "title": er_risk.title,
                        "status": status_value(getattr(er_risk, "status", None)),
                        "detail_path": f"/risk-register/{er_risk.id}",
                        "source": "control_standard_clauses",
                    }

        # Risks linked from matched findings (junction → risks_v2)
        if finding_ids:
            finding_rows = (
                (
                    await self.db.execute(
                        select(AuditFinding)
                        .options(selectinload(AuditFinding.risks))
                        .where(
                            AuditFinding.tenant_id == tenant_id,
                            AuditFinding.id.in_(finding_ids),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for finding in finding_rows:
                for linked_risk in finding.risks or []:
                    key = f"er-{linked_risk.id}"
                    matched[key] = {
                        "id": linked_risk.id,
                        "register": "enterprise",
                        "reference": linked_risk.reference,
                        "title": linked_risk.title,
                        "status": status_value(getattr(linked_risk, "status", None)),
                        "detail_path": f"/risk-register/{linked_risk.id}",
                        "source": "finding_link",
                        "from_finding_id": finding.id,
                    }

        return list(matched.values())

    async def _certs_for_framework(self, *, tenant_id: int, framework: str, clause_number: str) -> list[dict[str, Any]]:
        alias = FRAMEWORK_ALIASES.get(framework, {})
        schemes = {s.lower() for s in alias.get("cert_schemes", ())}
        shelf = await self.cert_shelf.get_shelf(tenant_id=tenant_id)
        items = shelf.get("items") or []
        matched: list[dict[str, Any]] = []
        clause_norm = normalize_clause_token(clause_number)
        for item in items:
            scheme = str(item.get("scheme") or "").strip().lower()
            if schemes and scheme not in schemes:
                continue
            metadata = item.get("metadata") or {}
            meta_clauses = metadata.get("clause_ids") or metadata.get("clauses") or []
            name = str(item.get("name") or "")
            proof_scope = "framework"
            if any_token_matches(meta_clauses, clause_match_keys(framework, clause_number), clause_number):
                proof_scope = "clause"
            elif clause_norm and clause_norm in normalize_clause_token(name):
                proof_scope = "clause"
            matched.append(
                {
                    **item,
                    "proof_scope": proof_scope,
                    "framework": framework,
                    "linked_clause": clause_number if proof_scope == "clause" else None,
                }
            )
        return matched

    async def _imported_priors(
        self, *, tenant_id: int, framework: str, finding_run_ids: set[int]
    ) -> list[dict[str, Any]]:
        alias = FRAMEWORK_ALIASES.get(framework, {})
        schemes = list(alias.get("record_schemes") or [])
        query = select(ExternalAuditRecord).where(
            or_(
                ExternalAuditRecord.tenant_id == tenant_id,
                ExternalAuditRecord.tenant_id.is_(None),
            )
        )
        if schemes:
            query = query.where(ExternalAuditRecord.scheme.in_(schemes))
        query = query.order_by(ExternalAuditRecord.report_date.desc().nullslast()).limit(50)
        rows = (await self.db.execute(query)).scalars().all()
        priors: list[dict[str, Any]] = []
        for record in rows:
            linked = bool(record.audit_run_id and record.audit_run_id in finding_run_ids)
            priors.append(
                {
                    "id": record.id,
                    "scheme": record.scheme,
                    "scheme_label": record.scheme_label,
                    "outcome_status": record.outcome_status,
                    "report_date": record.report_date.isoformat() if record.report_date else None,
                    "findings_count": record.findings_count,
                    "major_findings": record.major_findings,
                    "minor_findings": record.minor_findings,
                    "audit_run_id": record.audit_run_id,
                    "import_job_id": record.import_job_id,
                    "linked_to_cell_findings": linked,
                    "detail_path": (
                        f"/audits/{record.audit_run_id}/import-review"
                        + (f"?jobId={record.import_job_id}" if record.import_job_id else "")
                        if record.audit_run_id
                        else "/compliance?view=evidence&section=imported"
                    ),
                }
            )
        return priors
