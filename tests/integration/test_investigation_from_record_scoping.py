"""Investigation create-from-record: tenant scoping and a linkable conflict (PX-136).

Two defects are covered here:

1. The duplicate check ran across every tenant, so another organisation's investigation
   could report "an investigation already exists" for an incident this tenant had never
   investigated — and creation was blocked.
2. The 409 carried no machine-readable code or ids, so the "Open existing investigation"
   route out of the conflict could never fire and the operator was left stuck.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.asyncio, pytest.mark.requires_db]


async def _other_tenant_id(test_session) -> int:
    """Create a second tenant so cross-tenant rows satisfy the FK."""
    from tests.factories import TenantFactory

    tenant = TenantFactory.build(
        name="Other Tenant",
        slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
        admin_email="admin@other.example.com",
        is_active=True,
    )
    test_session.add(tenant)
    await test_session.commit()
    await test_session.refresh(tenant)
    return int(tenant.id)


class TestDuplicateConflict:
    async def test_conflict_carries_the_existing_investigation(
        self, admin_client: AsyncClient, near_miss_factory
    ) -> None:
        near_miss = await near_miss_factory()
        source_id = near_miss["id"]
        payload = {
            "source_type": "near_miss",
            "source_id": source_id,
            "title": "First investigation",
        }

        created = await admin_client.post("/api/v1/investigations/from-record", json=payload)
        assert created.status_code == 201, created.text

        conflict = await admin_client.post("/api/v1/investigations/from-record", json=payload)
        assert conflict.status_code == 409, conflict.text

        error = conflict.json()["error"]
        assert error["code"] == "INV_ALREADY_EXISTS"
        assert error["details"]["existing_investigation_id"] == created.json()["id"]
        assert error["details"]["existing_reference_number"] == created.json()["reference_number"]
        assert error["details"]["source_id"] == source_id


class TestTenantScoping:
    async def test_another_tenants_investigation_does_not_block_creation(
        self, admin_client: AsyncClient, test_session, near_miss_factory
    ) -> None:
        from src.domain.models.investigation import (
            AssignedEntityType,
            InvestigationRun,
            InvestigationStatus,
            InvestigationTemplate,
        )

        near_miss = await near_miss_factory()
        source_id = near_miss["id"]
        other_tenant_id = await _other_tenant_id(test_session)

        template = InvestigationTemplate(
            name="Other tenant template",
            version="1.0",
            is_active=True,
            structure={"sections": []},
            applicable_entity_types=[e.value for e in AssignedEntityType],
            created_by_id=1,
            updated_by_id=1,
            tenant_id=other_tenant_id,
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        # Same source id, different tenant. This must be invisible to tenant 1.
        test_session.add(
            InvestigationRun(
                template_id=template.id,
                assigned_entity_type=AssignedEntityType.NEAR_MISS,
                assigned_entity_id=source_id,
                title="Other tenant investigation",
                status=InvestigationStatus.DRAFT,
                data={},
                version=1,
                reference_number=f"INV-OTHER-{uuid.uuid4().hex[:6]}",
                tenant_id=other_tenant_id,
                created_by_id=1,
                updated_by_id=1,
            )
        )
        await test_session.commit()

        response = await admin_client.post(
            "/api/v1/investigations/from-record",
            json={
                "source_type": "near_miss",
                "source_id": source_id,
                "title": "Our investigation",
            },
        )

        assert response.status_code == 201, response.text


class TestSourceCoverage:
    async def test_reports_records_with_no_investigation(self, admin_client: AsyncClient, near_miss_factory) -> None:
        investigated = await near_miss_factory()
        await near_miss_factory()  # left uninvestigated on purpose

        created = await admin_client.post(
            "/api/v1/investigations/from-record",
            json={
                "source_type": "near_miss",
                "source_id": investigated["id"],
                "title": "Covered",
            },
        )
        assert created.status_code == 201, created.text

        response = await admin_client.get("/api/v1/investigations/source-coverage")
        assert response.status_code == 200, response.text

        body = response.json()
        near_miss_row = next(i for i in body["items"] if i["source_type"] == "near_miss")
        assert near_miss_row["total"] >= 2
        assert near_miss_row["investigated"] >= 1
        assert near_miss_row["not_investigated"] >= 1
        assert near_miss_row["investigated"] + near_miss_row["not_investigated"] == near_miss_row["total"]
        assert body["not_investigated"] == sum(i["not_investigated"] for i in body["items"])
