"""Helpers for complaint ↔ enterprise risk register bidirectional linking."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.complaint import Complaint
from src.domain.models.risk_register import EnterpriseRisk
from src.domain.services.case_risk_links import upsert_case_risk_link
from src.domain.services.near_miss_risk_links import (
    map_treatment_strategy,
    resolve_enterprise_category,
    resolve_fk_safe_owner_id,
)
from src.domain.services.reference_number import ReferenceNumberService

COMPLAINT_RISK_SOURCE_PREFIX = "complaint:"

_COMPLAINT_SOURCE_RE = re.compile(rf"^{re.escape(COMPLAINT_RISK_SOURCE_PREFIX)}(\d+)(?:\|(.+))?$")


def parse_linked_risk_ids(raw: Optional[str]) -> list[int]:
    """Parse comma-separated linked_risk_ids text into unique int IDs."""
    if not raw:
        return []
    ids: list[int] = []
    seen: set[int] = set()
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
        except ValueError:
            continue
        if value not in seen:
            seen.add(value)
            ids.append(value)
    return ids


def append_linked_risk_id(raw: Optional[str], risk_id: int) -> str:
    """Return updated linked_risk_ids text including risk_id (idempotent)."""
    ids = parse_linked_risk_ids(raw)
    if risk_id not in ids:
        ids.append(risk_id)
    return ",".join(str(i) for i in ids)


def complaint_risk_source(complaint_id: int, reference_number: str | None = None) -> str:
    """Canonical EnterpriseRisk.source/context encoding the originating complaint."""
    ref = (reference_number or "").strip()
    if ref:
        return f"{COMPLAINT_RISK_SOURCE_PREFIX}{complaint_id}|{ref}"
    return f"{COMPLAINT_RISK_SOURCE_PREFIX}{complaint_id}"


def parse_complaint_id_from_risk_source(risk_source: Optional[str]) -> Optional[int]:
    """Extract complaint id from risk_source when encoded by complaint_risk_source()."""
    if not risk_source:
        return None
    match = _COMPLAINT_SOURCE_RE.match(str(risk_source).strip())
    if not match:
        return None
    return int(match.group(1))


def complaint_detail_href(complaint_id: int) -> str:
    return f"/complaints/{complaint_id}"


def risk_register_href(risk_id: int | None = None, *, complaint_ref: str | None = None) -> str:
    if risk_id is None and not complaint_ref:
        return "/risk-register"
    params: list[str] = []
    if risk_id is not None:
        params.append(f"riskId={risk_id}")
    if complaint_ref:
        params.append(f"complaintRef={complaint_ref}")
    return "/risk-register?" + "&".join(params)


async def create_enterprise_risk_from_complaint(
    db: AsyncSession,
    *,
    complaint: Complaint,
    actor_user_id: int,
    title: str,
    description: str,
    likelihood: int,
    impact: int,
    category: str,
    treatment_strategy: str,
) -> EnterpriseRisk:
    """Create an EnterpriseRisk (risks_v2) linked to a complaint — parity with NM/Incident."""
    score = max(1, min(25, likelihood * impact))
    residual_likelihood = max(1, likelihood - 1)
    residual_score = max(1, residual_likelihood * impact)
    owner_id = await resolve_fk_safe_owner_id(
        db,
        preferred_owner_id=complaint.owner_id,
        fallback_user_id=actor_user_id,
    )
    source = complaint_risk_source(complaint.id, complaint.reference_number)
    linked_cases = [complaint.reference_number] if complaint.reference_number else []

    risk = EnterpriseRisk(
        tenant_id=complaint.tenant_id,
        reference=await ReferenceNumberService.generate(db, "risk", EnterpriseRisk),
        title=title[:255],
        description=description,
        category=resolve_enterprise_category(category, "compliance"),
        subcategory="complaint",
        source="complaint",
        context=source,
        department=complaint.department,
        location=None,
        process="complaint escalation",
        inherent_likelihood=likelihood,
        inherent_impact=impact,
        inherent_score=score,
        residual_likelihood=residual_likelihood,
        residual_impact=impact,
        residual_score=residual_score,
        risk_appetite="cautious",
        appetite_threshold=12,
        is_within_appetite=score <= 12,
        treatment_strategy=map_treatment_strategy(treatment_strategy),
        treatment_plan=(
            f"Raised from complaint {complaint.reference_number}. " "Review in Risk Register and set treatment plan."
        ),
        risk_owner_id=owner_id,
        status="open",
        review_frequency_days=30,
        next_review_date=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30),
        is_escalated=True,
        escalation_reason=f"Raised from complaint {complaint.reference_number}",
        escalation_date=datetime.now(timezone.utc).replace(tzinfo=None),
        linked_incidents=linked_cases,
        linked_audits=[],
        linked_actions=[],
        created_by=actor_user_id,
    )
    db.add(risk)
    await db.flush()
    if complaint.tenant_id is not None:
        await upsert_case_risk_link(
            db,
            tenant_id=complaint.tenant_id,
            case_type="complaint",
            case_id=complaint.id,
            risk_id=risk.id,
        )
    return risk
