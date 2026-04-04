#!/usr/bin/env python3
"""Ensure Locust/CI default accounts exist after Alembic migrations (idempotent)."""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from src.core.security import get_password_hash
from src.domain.models.tenant import Tenant, TenantUser
from src.domain.models.user import User
from src.infrastructure.database import async_session_maker


async def _ensure() -> None:
    async with async_session_maker() as db:
        res = await db.execute(select(Tenant).where(Tenant.is_active.is_(True)).order_by(Tenant.id.asc()).limit(1))
        tenant = res.scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(
                name="CI Load Test",
                slug="ci-load-test",
                admin_email="admin@plantexpand.com",
                is_active=True,
            )
            db.add(tenant)
            await db.flush()

        async def upsert(email: str, password: str, *, superuser: bool) -> None:
            r = await db.execute(select(User).where(User.email == email))
            user = r.scalar_one_or_none()
            hp = get_password_hash(password)
            if user is None:
                user = User(
                    email=email,
                    hashed_password=hp,
                    first_name="CI",
                    last_name="User",
                    is_active=True,
                    is_superuser=superuser,
                    tenant_id=tenant.id,
                )
                db.add(user)
            else:
                user.hashed_password = hp
                user.is_active = True
                user.is_superuser = superuser
                user.tenant_id = tenant.id
            await db.flush()

            r2 = await db.execute(
                select(TenantUser).where(
                    TenantUser.user_id == user.id,
                    TenantUser.tenant_id == tenant.id,
                )
            )
            if r2.scalar_one_or_none() is None:
                db.add(
                    TenantUser(
                        tenant_id=tenant.id,
                        user_id=user.id,
                        is_active=True,
                        is_primary=True,
                        role="owner" if superuser else "user",
                    )
                )

        await upsert("admin@plantexpand.com", "adminpassword123", superuser=True)
        await upsert("testuser@plantexpand.com", "testpassword123", superuser=False)
        await db.commit()


def main() -> int:
    try:
        asyncio.run(_ensure())
    except Exception as exc:  # noqa: BLE001 — script entrypoint
        print(f"[seed_ci_locust_users] failed: {exc}", file=sys.stderr)
        return 1
    print("[seed_ci_locust_users] ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
