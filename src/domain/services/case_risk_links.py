"""Normalized case ↔ enterprise risk junction helpers (dual-write MVP)."""

from __future__ import annotations

from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.risk_register import CaseRiskLink

CaseType = Literal["incident", "near_miss", "rta", "complaint"]


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


async def upsert_case_risk_link(
    db: AsyncSession,
    *,
    tenant_id: int,
    case_type: CaseType,
    case_id: int,
    risk_id: int,
) -> None:
    """Insert junction row idempotently; no-op when link already exists."""
    if tenant_id is None or case_id is None or risk_id is None:
        return

    bind = db.get_bind()
    dialect_name = getattr(getattr(bind, "dialect", None), "name", None)

    if dialect_name == "postgresql":
        stmt = (
            pg_insert(CaseRiskLink)
            .values(
                tenant_id=tenant_id,
                case_type=case_type,
                case_id=case_id,
                risk_id=risk_id,
            )
            .on_conflict_do_nothing(constraint="uq_case_risk_links_tenant_case_risk")
        )
        await db.execute(stmt)
        return

    existing = await db.execute(
        select(CaseRiskLink.id).where(
            CaseRiskLink.tenant_id == tenant_id,
            CaseRiskLink.case_type == case_type,
            CaseRiskLink.case_id == case_id,
            CaseRiskLink.risk_id == risk_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(
            CaseRiskLink(
                tenant_id=tenant_id,
                case_type=case_type,
                case_id=case_id,
                risk_id=risk_id,
            )
        )


async def sync_case_risk_links_from_csv(
    db: AsyncSession,
    *,
    tenant_id: int,
    case_type: CaseType,
    case_id: int,
    linked_risk_ids_raw: Optional[str],
) -> None:
    """Upsert junction rows for every parsed linked_risk_ids entry."""
    for risk_id in parse_linked_risk_ids(linked_risk_ids_raw):
        await upsert_case_risk_link(
            db,
            tenant_id=tenant_id,
            case_type=case_type,
            case_id=case_id,
            risk_id=risk_id,
        )


async def get_case_linked_risk_ids(
    db: AsyncSession,
    *,
    tenant_id: int,
    case_type: CaseType,
    case_id: int,
    csv_fallback: Optional[str] = None,
) -> list[int]:
    """Prefer junction rows; fall back to legacy CSV when junction is empty."""
    if tenant_id is not None:
        result = await db.execute(
            select(CaseRiskLink.risk_id)
            .where(
                CaseRiskLink.tenant_id == tenant_id,
                CaseRiskLink.case_type == case_type,
                CaseRiskLink.case_id == case_id,
            )
            .order_by(CaseRiskLink.risk_id)
        )
        ids = [row[0] for row in result.all()]
        if ids:
            return ids
    return parse_linked_risk_ids(csv_fallback)


async def list_case_links_for_risk(
    db: AsyncSession,
    *,
    tenant_id: int,
    risk_id: int,
) -> list[CaseRiskLink]:
    """Reverse lookup: cases linked to an enterprise risk (newest first)."""
    result = await db.execute(
        select(CaseRiskLink)
        .where(
            CaseRiskLink.tenant_id == tenant_id,
            CaseRiskLink.risk_id == risk_id,
        )
        .order_by(CaseRiskLink.created_at.desc(), CaseRiskLink.id.desc())
    )
    return list(result.scalars().all())


def case_type_href(case_type: str, case_id: int) -> str:
    """Deep-link path for a case_risk_links case_type."""
    mapping = {
        "incident": f"/incidents/{case_id}",
        "near_miss": f"/near-misses/{case_id}",
        "rta": f"/rtas/{case_id}",
        "complaint": f"/complaints/{case_id}",
    }
    return mapping.get(case_type, f"/{case_type}/{case_id}")
