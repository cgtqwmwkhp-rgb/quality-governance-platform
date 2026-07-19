"""Helpers for incident ↔ enterprise risk register bidirectional linking."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError
from src.domain.models.enums import EnterpriseRiskStatus
from src.domain.models.incident import Incident, IncidentSeverity
from src.domain.models.risk_register import EnterpriseRisk
from src.domain.models.user import User
from src.domain.services.case_risk_links import upsert_case_risk_link
from src.domain.services.reference_number import ReferenceNumberService

INCIDENT_RISK_SOURCE_PREFIX = "incident:"

# Severities eligible for guided raise-risk (configurable extension point).
RAISE_RISK_ALLOWED_SEVERITIES: frozenset[str] = frozenset({"high", "critical"})

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

_INCIDENT_TYPE_CATEGORY = {
    "environmental": "environmental",
    "security": "information_security",
    "quality": "compliance",
    "injury": "safety",
    "near_miss": "safety",
    "hazard": "safety",
    "property_damage": "operational",
}

_SEVERITY_IMPACT = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "negligible": 1,
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


def incident_risk_source(incident_id: int, reference_number: str | None = None) -> str:
    """Canonical EnterpriseRisk.context encoding the originating incident."""
    ref = (reference_number or "").strip()
    if ref:
        return f"{INCIDENT_RISK_SOURCE_PREFIX}{incident_id}|{ref}"
    return f"{INCIDENT_RISK_SOURCE_PREFIX}{incident_id}"


_INCIDENT_SOURCE_RE = re.compile(rf"^{re.escape(INCIDENT_RISK_SOURCE_PREFIX)}(\d+)(?:\|(.+))?$")


def parse_incident_id_from_risk_context(risk_context: Optional[str]) -> Optional[int]:
    """Extract incident id from context when encoded by incident_risk_source()."""
    if not risk_context:
        return None
    match = _INCIDENT_SOURCE_RE.match(str(risk_context).strip())
    if not match:
        return None
    return int(match.group(1))


def incident_detail_href(incident_id: int) -> str:
    return f"/incidents/{incident_id}"


def risk_register_href(risk_id: int | None = None, *, incident_ref: str | None = None) -> str:
    if risk_id is None and not incident_ref:
        return "/risk-register"
    params: list[str] = []
    if risk_id is not None:
        params.append(f"riskId={risk_id}")
    if incident_ref:
        params.append(f"incidentRef={incident_ref}")
    return "/risk-register?" + "&".join(params)


def map_treatment_strategy(raw: str | None) -> str:
    """Map legacy raise-risk treatment values onto enterprise register strategies."""
    key = (raw or "treat").strip().lower()
    return _TREATMENT_MAP.get(key, "treat")


def severity_allows_raise_risk(severity: IncidentSeverity | str | None) -> bool:
    """Return True when incident severity is eligible for enterprise raise-risk."""
    if severity is None:
        return False
    value = str(getattr(severity, "value", severity)).strip().lower()
    return value in RAISE_RISK_ALLOWED_SEVERITIES


def resolve_enterprise_category(preferred: str | None, incident: Incident) -> str:
    incident_type = str(getattr(incident.incident_type, "value", incident.incident_type) or "").lower()
    type_default = _INCIDENT_TYPE_CATEGORY.get(incident_type)
    for candidate in (preferred, type_default, "safety"):
        if not candidate:
            continue
        value = str(candidate).strip().lower()
        if value in _ENTERPRISE_CATEGORIES:
            return value
    return "safety"


def default_impact_for_incident(incident: Incident, override: int | None = None) -> int:
    if override is not None and override != 3:
        return max(1, min(5, override))
    severity = str(getattr(incident.severity, "value", incident.severity) or "medium").lower()
    return _SEVERITY_IMPACT.get(severity, 3)


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


async def find_existing_enterprise_risk_for_incident(
    db: AsyncSession,
    *,
    incident: Incident,
) -> EnterpriseRisk | None:
    """Return an existing enterprise risk for this incident (CSV link or context), if any."""
    for risk_id in parse_linked_risk_ids(incident.linked_risk_ids):
        result = await db.execute(select(EnterpriseRisk).where(EnterpriseRisk.id == risk_id))
        risk = result.scalar_one_or_none()
        if risk is not None:
            return risk

    source = incident_risk_source(incident.id, incident.reference_number)
    result = await db.execute(
        select(EnterpriseRisk).where(EnterpriseRisk.context == source).order_by(EnterpriseRisk.id.asc()).limit(1)
    )
    return result.scalar_one_or_none()


async def create_enterprise_risk_from_incident(
    db: AsyncSession,
    *,
    incident: Incident,
    actor_user_id: int,
    title: str,
    description: str,
    likelihood: int,
    impact: int,
    category: str,
    treatment_strategy: str,
    tenant_id: int | None = None,
) -> EnterpriseRisk:
    """Create an EnterpriseRisk (risks_v2) linked to an incident — canonical UI path."""
    resolved_tenant_id = tenant_id if tenant_id is not None else incident.tenant_id
    if resolved_tenant_id is None:
        raise BadRequestError("Incident has no tenant; cannot raise an enterprise risk.")

    score = max(1, min(25, likelihood * impact))
    residual_likelihood = max(1, likelihood - 1)
    residual_score = max(1, residual_likelihood * impact)
    owner_id = await resolve_fk_safe_owner_id(
        db,
        preferred_owner_id=incident.owner_id,
        fallback_user_id=actor_user_id,
    )
    source = incident_risk_source(incident.id, incident.reference_number)
    linked_cases = [incident.reference_number] if incident.reference_number else []

    risk = EnterpriseRisk(
        tenant_id=resolved_tenant_id,
        reference=await ReferenceNumberService.generate(db, "risk", EnterpriseRisk),
        title=title[:255],
        description=description,
        category=resolve_enterprise_category(category, incident),
        subcategory="incident",
        source="incident",
        context=source,
        department=incident.department,
        location=incident.location,
        process="incident escalation",
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
            f"Raised from incident {incident.reference_number}. " "Review in Risk Register and set treatment plan."
        ),
        risk_owner_id=owner_id,
        status=EnterpriseRiskStatus.IDENTIFIED.value,
        review_frequency_days=30,
        next_review_date=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30),
        is_escalated=True,
        escalation_reason=f"Raised from incident {incident.reference_number}",
        escalation_date=datetime.now(timezone.utc).replace(tzinfo=None),
        linked_incidents=linked_cases,
        linked_audits=[],
        linked_actions=[],
        created_by=actor_user_id,
    )
    db.add(risk)
    await db.flush()
    await upsert_case_risk_link(
        db,
        tenant_id=resolved_tenant_id,
        case_type="incident",
        case_id=incident.id,
        risk_id=risk.id,
    )
    return risk
