"""Resolve customer lookup codes to contracts.id for case FKs."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.form_config import Contract, LookupOption


async def resolve_contract_id_by_code(
    db: AsyncSession,
    *,
    tenant_id: int,
    code: Optional[str],
) -> Optional[int]:
    """Return contracts.id for tenant+code, or None if blank/unknown.

    Contract.code is globally unique; only link when the row belongs to the tenant.
    If missing, create from customers lookup (tenant then global).
    """
    normalized = (code or "").strip()
    if not normalized or normalized.lower() in {"other", "unknown"}:
        return None

    existing = (
        await db.execute(select(Contract).where(func.lower(Contract.code) == normalized.lower()))
    ).scalar_one_or_none()
    if existing is not None:
        if existing.tenant_id == tenant_id:
            return int(existing.id)
        return None

    lookup = (
        await db.execute(
            select(LookupOption).where(
                LookupOption.tenant_id == tenant_id,
                LookupOption.category == "customers",
                func.lower(LookupOption.code) == normalized.lower(),
                LookupOption.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if lookup is None:
        lookup = (
            await db.execute(
                select(LookupOption).where(
                    LookupOption.tenant_id.is_(None),
                    LookupOption.category == "customers",
                    func.lower(LookupOption.code) == normalized.lower(),
                    LookupOption.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
    if lookup is None:
        return None

    contract = Contract(
        tenant_id=tenant_id,
        code=lookup.code,
        name=lookup.label or lookup.code,
        description=lookup.description,
        is_active=True,
        display_order=lookup.display_order or 0,
    )
    try:
        async with db.begin_nested():
            db.add(contract)
            await db.flush()
    except IntegrityError:
        raced = (
            await db.execute(select(Contract).where(func.lower(Contract.code) == normalized.lower()))
        ).scalar_one_or_none()
        if raced is not None and raced.tenant_id == tenant_id:
            return int(raced.id)
        return None
    return int(contract.id)


async def ensure_contracts_from_customer_lookups(
    db: AsyncSession,
    *,
    tenant_id: int,
) -> int:
    """Materialise contracts.id rows for active Admin → Lookups → Customers options.

    Staff incident/complaint dropdowns read ``/admin/config/contracts`` while admins
    configure customers in the lookups catalog. Without this bridge, the contracts
    table can stay empty even when customers are live.
    """
    created_or_linked = 0
    result = await db.execute(
        select(LookupOption).where(
            LookupOption.tenant_id == tenant_id,
            LookupOption.category == "customers",
            LookupOption.is_active.is_(True),
        )
    )
    for lookup in result.scalars().all():
        resolved = await resolve_contract_id_by_code(db, tenant_id=tenant_id, code=lookup.code)
        if resolved is not None:
            created_or_linked += 1
    return created_or_linked


async def assert_tenant_contract(
    db: AsyncSession,
    *,
    contract_id: int,
    tenant_id: int,
) -> None:
    result = await db.execute(select(Contract.id).where(Contract.id == contract_id, Contract.tenant_id == tenant_id))
    if result.scalar_one_or_none() is None:
        raise ValueError(f"Contract with ID {contract_id} not found")
