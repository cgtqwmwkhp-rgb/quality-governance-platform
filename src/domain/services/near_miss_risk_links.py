"""Helpers for near-miss ↔ enterprise risk register bidirectional linking."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.near_miss import NearMiss
from src.domain.models.risk_register import EnterpriseRisk
from src.domain.models.user import User
from src.domain.services.case_risk_links import upsert_case_risk_link
from src.domain.services.reference_number import ReferenceNumberService

NEAR_MISS_RISK_SOURCE_PREFIX = "near_miss:"

# Legacy raise-risk request values → enterprise Risk Register strategies.
_TREATMENT_MAP = {
    "mitigate": "treat",
    "accept": "tolerate",
    "transfer": "transfer",
    "avoid": "terminate",
    "exploit": "treat",
    "treat": "treat",
    "tolerate": "tolerate",
    "terminate": "terminate",
}

_ENTERPRISE_CATEGORIES = {
    "strategic",
    "operational",
    "financial",
    "compliance",
    "reputational",
    "safety",
    "environmental",
    "information_security",
}


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


def near_miss_risk_source(near_miss_id: int, reference_number: str | None = None) -> str:
    """Canonical EnterpriseRisk.source/context encoding the originating near miss."""
    ref = (reference_number or "").strip()
    if ref:
        return f"{NEAR_MISS_RISK_SOURCE_PREFIX}{near_miss_id}|{ref}"
    return f"{NEAR_MISS_RISK_SOURCE_PREFIX}{near_miss_id}"


_NEAR_MISS_SOURCE_RE = re.compile(rf"^{re.escape(NEAR_MISS_RISK_SOURCE_PREFIX)}(\d+)(?:\|(.+))?$")


def parse_near_miss_id_from_risk_source(risk_source: Optional[str]) -> Optional[int]:
    """Extract near_miss id from risk_source when encoded by near_miss_risk_source()."""
    if not risk_source:
        return None
    match = _NEAR_MISS_SOURCE_RE.match(str(risk_source).strip())
    if not match:
        return None
    return int(match.group(1))


def near_miss_detail_href(near_miss_id: int) -> str:
    return f"/near-misses/{near_miss_id}"


def risk_register_href(risk_id: int | None = None, *, near_miss_ref: str | None = None) -> str:
    if risk_id is None and not near_miss_ref:
        return "/risk-register"
    params: list[str] = []
    if risk_id is not None:
        params.append(f"riskId={risk_id}")
    if near_miss_ref:
        params.append(f"nearMissRef={near_miss_ref}")
    return "/risk-register?" + "&".join(params)


def map_treatment_strategy(raw: str | None) -> str:
    """Map legacy raise-risk treatment values onto enterprise register strategies."""
    key = (raw or "treat").strip().lower()
    return _TREATMENT_MAP.get(key, "treat")


def resolve_enterprise_category(preferred: str | None, near_miss_category: str | None) -> str:
    for candidate in (near_miss_category, preferred, "safety"):
        if not candidate:
            continue
        value = str(candidate).strip().lower()
        if value in _ENTERPRISE_CATEGORIES:
            return value
    return "safety"


async def resolve_fk_safe_owner_id(
    db: AsyncSession,
    *,
    preferred_owner_id: int | None,
    fallback_user_id: int | None,
) -> int | None:
    """Return a user id that exists in `users`, else None (avoids IntegrityError 500s)."""
    for candidate in (preferred_owner_id, fallback_user_id):
        if candidate is None:
            continue
        result = await db.execute(select(User.id).where(User.id == candidate))
        if result.scalar_one_or_none() is not None:
            return candidate
    return None


async def create_enterprise_risk_from_near_miss(
    db: AsyncSession,
    *,
    near_miss: NearMiss,
    actor_user_id: int,
    title: str,
    description: str,
    likelihood: int,
    impact: int,
    category: str,
    treatment_strategy: str,
) -> EnterpriseRisk:
    """Create an EnterpriseRisk (risks_v2) linked to a near miss — canonical UI path."""
    score = max(1, min(25, likelihood * impact))
    residual_likelihood = max(1, likelihood - 1)
    residual_score = max(1, residual_likelihood * impact)
    owner_id = await resolve_fk_safe_owner_id(
        db,
        preferred_owner_id=near_miss.assigned_to_id,
        fallback_user_id=actor_user_id,
    )
    source = near_miss_risk_source(near_miss.id, near_miss.reference_number)
    linked_cases = [near_miss.reference_number] if near_miss.reference_number else []

    risk = EnterpriseRisk(
        tenant_id=near_miss.tenant_id,
        reference=await ReferenceNumberService.generate(db, "risk", EnterpriseRisk),
        title=title[:255],
        description=description,
        category=resolve_enterprise_category(category, near_miss.risk_category),
        subcategory="near_miss",
        source="near_miss",
        context=source,
        department=None,
        location=near_miss.location,
        process="near miss escalation",
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
            f"Raised from near miss {near_miss.reference_number}. " "Review in Risk Register and set treatment plan."
        ),
        risk_owner_id=owner_id,
        status="open",
        review_frequency_days=30,
        next_review_date=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30),
        is_escalated=True,
        escalation_reason=f"Raised from near miss {near_miss.reference_number}",
        escalation_date=datetime.now(timezone.utc).replace(tzinfo=None),
        linked_incidents=linked_cases,
        linked_audits=[],
        linked_actions=[],
        created_by=actor_user_id,
    )
    db.add(risk)
    await db.flush()
    if near_miss.tenant_id is not None:
        await upsert_case_risk_link(
            db,
            tenant_id=near_miss.tenant_id,
            case_type="near_miss",
            case_id=near_miss.id,
            risk_id=risk.id,
        )
    return risk
