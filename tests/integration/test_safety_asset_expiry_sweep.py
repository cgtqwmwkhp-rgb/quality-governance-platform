"""The safety-asset expiry sweep must notify the right people and nobody else.

Exercised against a real session rather than mocks, because the property that
matters is a property of the recipient query: that an administrator belonging to
no tenant is never told about a tenant's safety assets. The sweep resolved
admins with ``tenant_id IS NULL OR tenant_id = :asset_tenant``, so a NULL-tenant
service account received notifications naming *every* tenant's assets by number
and name. A test that only checked "the owner was notified" passes against that.

The sweep runs on the **synchronous** ``SessionLocal``, while these tests set up
and assert through the async ``test_session``. Both are built from the same
``DATABASE_URL`` -- ``to_sync_database_url`` only swaps the driver -- so they
address the same database. The consequence for test authors is that setup must
be *committed*, and the async session must not be holding a transaction open
when the sweep runs, or SQLite will refuse the sweep's write.

Rows are removed explicitly in teardown: the integration conftest only calls
``drop_all`` on SQLite, so on PostgreSQL anything committed here survives into
every later test in the run. For the same reason every assertion is scoped to an
asset or user id created by the test rather than to a global count.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from src.domain.models.asset import Asset, AssetCategory, AssetType
from src.domain.models.notification import Notification
from src.domain.models.user import Role, User, user_roles
from src.infrastructure.tasks.safety_asset_expiry_tasks import ENTITY_TYPE, check_safety_asset_expiry


class _World:
    """Builds the rows a test needs and remembers them for teardown."""

    def __init__(self, session):
        self._session = session
        self.tenant_ids: list[int] = []
        self.user_ids: list[int] = []
        self.asset_ids: list[int] = []
        self.asset_type_ids: list[int] = []
        self.created_role_ids: list[int] = []

    async def tenant(self) -> int:
        from tests.factories import TenantFactory

        tenant = TenantFactory.build(
            name="Safety Expiry Tenant",
            slug=f"safety-expiry-{uuid.uuid4().hex[:8]}",
            admin_email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            is_active=True,
        )
        self._session.add(tenant)
        await self._session.commit()
        await self._session.refresh(tenant)
        self.tenant_ids.append(tenant.id)
        return tenant.id

    async def admin_role(self) -> Role:
        rows = await self._session.execute(select(Role).where(Role.name == "admin"))
        role = rows.scalars().first()
        if role is not None:
            return role
        # Created rather than skipped. Skipping would retire the only tests that
        # catch a cross-tenant leak on whichever harness happens to lack the row,
        # which is the SQLite one the suite uses by default.
        role = Role(name="admin", description="Test admin role", is_system_role=False)
        self._session.add(role)
        await self._session.commit()
        await self._session.refresh(role)
        self.created_role_ids.append(role.id)
        return role

    async def user(
        self,
        *,
        tenant_id: int | None,
        admin: bool = False,
        is_active: bool = True,
        deleted: bool = False,
        label: str = "user",
    ) -> int:
        from src.core.security import get_password_hash

        person = User(
            email=f"{label}-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("testpassword123"),
            first_name=label.title(),
            last_name="Recipient",
            is_active=is_active,
            is_superuser=False,
            tenant_id=tenant_id,
        )
        if deleted:
            person.deleted_at = datetime.now(timezone.utc)
        if admin:
            person.roles.append(await self.admin_role())
        self._session.add(person)
        await self._session.commit()
        await self._session.refresh(person)
        self.user_ids.append(person.id)
        return person.id

    async def safety_asset(
        self,
        *,
        tenant_id: int | None,
        owner_user_id: int | None = None,
        days_overdue: int = 40,
    ) -> int:
        suffix = uuid.uuid4().hex[:8]
        asset_type = AssetType(
            category=AssetCategory.SAFETY,
            name=f"Fire Extinguisher {suffix}",
            is_active=True,
            tenant_id=tenant_id,
        )
        self._session.add(asset_type)
        await self._session.commit()
        await self._session.refresh(asset_type)
        self.asset_type_ids.append(asset_type.id)

        asset = Asset(
            asset_type_id=asset_type.id,
            asset_number=f"SA-{suffix}",
            name=f"CO2 Extinguisher {suffix}",
            expiry_date=datetime.now(timezone.utc) - timedelta(days=days_overdue),
            owner_user_id=owner_user_id,
            tenant_id=tenant_id,
        )
        self._session.add(asset)
        await self._session.commit()
        await self._session.refresh(asset)
        self.asset_ids.append(asset.id)
        return asset.id

    async def notifications_for(self, asset_id: int) -> list[Notification]:
        """Notifications naming one asset.

        Scoped to the asset rather than to ``entity_type`` alone because on
        PostgreSQL every row an earlier test committed is still present, and an
        unrelated safety asset left behind elsewhere would fail these assertions
        for reasons that have nothing to do with the sweep.
        """
        rows = await self._session.execute(
            select(Notification).where(
                Notification.entity_type == ENTITY_TYPE,
                Notification.entity_id == str(asset_id),
            )
        )
        return list(rows.scalars().all())

    async def sweep(self) -> dict:
        """Run the real task body against the database.

        The rollback is not tidiness: the sweep writes through a *different*
        connection, and an open read transaction on this one is enough for SQLite
        to refuse it with "database is locked".
        """
        await self._session.rollback()
        return check_safety_asset_expiry.run()

    async def teardown(self) -> None:
        await self._session.rollback()
        if self.asset_ids:
            await self._session.execute(
                delete(Notification).where(
                    Notification.entity_type == ENTITY_TYPE,
                    Notification.entity_id.in_([str(asset_id) for asset_id in self.asset_ids]),
                )
            )
            await self._session.execute(delete(Asset).where(Asset.id.in_(self.asset_ids)))
        if self.user_ids:
            await self._session.execute(delete(Notification).where(Notification.user_id.in_(self.user_ids)))
        if self.asset_type_ids:
            await self._session.execute(delete(AssetType).where(AssetType.id.in_(self.asset_type_ids)))
        if self.user_ids:
            # The association rows go with a Core delete rather than
            # ``user.roles.clear()``: touching that collection on an expired
            # instance triggers a lazy load, which raises MissingGreenlet on an
            # async session and turns teardown into a test failure.
            await self._session.execute(delete(user_roles).where(user_roles.c.user_id.in_(self.user_ids)))
            await self._session.execute(delete(User).where(User.id.in_(self.user_ids)))
        if self.tenant_ids:
            await self._session.execute(delete(Asset).where(Asset.tenant_id.in_(self.tenant_ids)))
        if self.created_role_ids:
            await self._session.execute(delete(Role).where(Role.id.in_(self.created_role_ids)))
        await self._session.commit()


@pytest.fixture
async def world(test_session):
    built = _World(test_session)
    try:
        yield built
    finally:
        await built.teardown()


async def test_a_tenant_null_admin_is_never_notified_about_any_tenants_assets(world):
    """The cross-tenant leak guard, with two tenants in play.

    A NULL-tenant admin is what a service or ETL account looks like, and the
    obvious implementation -- ``tenant_id IS NULL OR tenant_id = :tenant`` --
    hands them every tenant's asset register by name.
    """
    tenant_a = await world.tenant()
    tenant_b = await world.tenant()
    stray_admin_id = await world.user(tenant_id=None, admin=True, label="etl-service")
    admin_a_id = await world.user(tenant_id=tenant_a, admin=True, label="admin-a")

    asset_a = await world.safety_asset(tenant_id=tenant_a)
    asset_b = await world.safety_asset(tenant_id=tenant_b)

    await world.sweep()

    for asset_id, tenant_id in ((asset_a, tenant_a), (asset_b, tenant_b)):
        leaked = [n for n in await world.notifications_for(asset_id) if n.user_id == stray_admin_id]
        assert leaked == [], (
            f"an admin belonging to no tenant received {len(leaked)} notification(s) naming "
            f"tenant {tenant_id}'s safety asset {asset_id}"
        )

    # Delivery to the tenant's own admin is unchanged, so a leak fix that simply
    # notified nobody would not pass here.
    delivered = [n for n in await world.notifications_for(asset_a) if n.user_id == admin_a_id]
    assert len(delivered) == 1, f"tenant {tenant_a}'s own admin got {len(delivered)} notifications, expected 1"


async def test_an_admin_is_notified_only_about_their_own_tenants_assets(world):
    """Neither tenant's admin may appear in the other tenant's notifications."""
    tenant_a = await world.tenant()
    tenant_b = await world.tenant()
    admin_a_id = await world.user(tenant_id=tenant_a, admin=True, label="admin-a")
    admin_b_id = await world.user(tenant_id=tenant_b, admin=True, label="admin-b")

    asset_a = await world.safety_asset(tenant_id=tenant_a)
    asset_b = await world.safety_asset(tenant_id=tenant_b)

    await world.sweep()

    recipients_a = {n.user_id for n in await world.notifications_for(asset_a)}
    recipients_b = {n.user_id for n in await world.notifications_for(asset_b)}

    assert recipients_a == {admin_a_id}, f"tenant {tenant_a}'s asset reached {recipients_a}"
    assert recipients_b == {admin_b_id}, f"tenant {tenant_b}'s asset reached {recipients_b}"


async def test_an_asset_belonging_to_no_tenant_reaches_no_admin(world):
    """A tenant-less asset names no tenant whose admins could be told about it.

    ``User.tenant_id == None`` renders as ``IS NULL`` in SQL, so scoping admins
    to the asset's tenant without a guard hands this asset every tenant-less
    user -- the same leak facing the other way.
    """
    tenant_a = await world.tenant()
    stray_admin_id = await world.user(tenant_id=None, admin=True, label="etl-service")
    await world.user(tenant_id=tenant_a, admin=True, label="admin-a")

    orphan_asset = await world.safety_asset(tenant_id=None)

    result = await world.sweep()

    delivered = await world.notifications_for(orphan_asset)
    assert delivered == [], f"a tenant-less asset reached {[n.user_id for n in delivered]}"
    assert stray_admin_id not in {n.user_id for n in delivered}
    assert result["recipients_unresolved"] >= 1, f"the unreachable asset was not counted: {result}"


async def test_a_soft_deleted_admin_is_not_notified(world):
    """``is_active`` and ``deleted_at`` are different questions; both must be asked."""
    tenant_a = await world.tenant()
    deleted_admin_id = await world.user(tenant_id=tenant_a, admin=True, deleted=True, label="deleted-admin")
    live_admin_id = await world.user(tenant_id=tenant_a, admin=True, label="live-admin")

    asset_a = await world.safety_asset(tenant_id=tenant_a)

    await world.sweep()

    recipients = {n.user_id for n in await world.notifications_for(asset_a)}
    assert deleted_admin_id not in recipients, "a soft-deleted admin was notified"
    assert live_admin_id in recipients, "the live admin was not notified, so this test proves nothing"


async def test_an_inactive_admin_is_not_notified(world):
    tenant_a = await world.tenant()
    inactive_admin_id = await world.user(tenant_id=tenant_a, admin=True, is_active=False, label="inactive-admin")
    live_admin_id = await world.user(tenant_id=tenant_a, admin=True, label="live-admin")

    asset_a = await world.safety_asset(tenant_id=tenant_a)

    await world.sweep()

    recipients = {n.user_id for n in await world.notifications_for(asset_a)}
    assert inactive_admin_id not in recipients, "an inactive admin was notified"
    assert live_admin_id in recipients, "the live admin was not notified, so this test proves nothing"


async def test_the_owner_is_still_notified_and_a_second_run_writes_nothing(world):
    """Delivery to an owner is untouched, and a redelivered run does not duplicate.

    ``task_acks_late`` means a worker lost mid-run has its task redelivered, so a
    second copy running over the same assets is an ordinary event rather than a
    hypothetical one.
    """
    tenant_a = await world.tenant()
    owner_id = await world.user(tenant_id=tenant_a, label="owner")

    asset_a = await world.safety_asset(tenant_id=tenant_a, owner_user_id=owner_id)

    await world.sweep()

    delivered = [n for n in await world.notifications_for(asset_a) if n.user_id == owner_id]
    assert len(delivered) == 1, f"the owner got {len(delivered)} notifications, expected 1"
    assert delivered[0].tenant_id == tenant_a
    assert delivered[0].extra_data and delivered[0].extra_data.get("band") == "overdue"

    second = await world.sweep()

    still = [n for n in await world.notifications_for(asset_a) if n.user_id == owner_id]
    assert len(still) == 1, f"a second run duplicated the owner's notification ({len(still)} rows): {second}"
    assert second["notifications_skipped_dedupe"] >= 1


async def test_a_tenant_with_no_admins_and_an_unowned_asset_notifies_nobody(world):
    """The production shape today: an overdue register nobody is configured to hear about."""
    tenant_a = await world.tenant()
    asset_a = await world.safety_asset(tenant_id=tenant_a)

    result = await world.sweep()

    assert await world.notifications_for(asset_a) == [], "an asset with no owner and no tenant admin reached someone"
    assert result["in_band"] >= 1, "the asset was not classified, so this test proves nothing"
    assert result["recipients_unresolved"] >= 1, f"the unreachable asset was not counted: {result}"
