"""Integration tests for Compliance Schedule API (Wave 1)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient

from src.core.config import settings
from src.domain.models.compliance_schedule import (
    ComplianceRequirementTemplate,
    ComplianceScheduleAnchor,
)
from src.domain.services.compliance_schedule_kill_switch import (
    reset_compliance_schedule_kill_switch_cache,
)


@pytest.fixture
def enable_compliance_schedule(monkeypatch):
    monkeypatch.setattr(settings, "compliance_schedule_enabled", True)
    reset_compliance_schedule_kill_switch_cache()
    yield
    reset_compliance_schedule_kill_switch_cache()


@pytest.fixture
async def seeded_template(test_session):
    template = ComplianceRequirementTemplate(
        tenant_id=None,
        template_key="wave1-fra",
        title="Fire Risk Assessment",
        taxonomy_id="HS-01",
        description="Annual FRA",
        regulatory_basis="Regulatory Reform (Fire Safety) Order 2005",
        frequency_months=12,
        frequency_days=None,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=True,
        is_active=True,
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)
    return template


def _cs_headers(permissions: str) -> dict[str, str]:
    from tests.integration.conftest import _generate_test_jwt

    token = _generate_test_jwt(
        user_id="1",
        role="admin",
        is_superuser=False,
        permissions=permissions,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_flag_off_returns_404(client: AsyncClient, auth_headers: dict, monkeypatch):
    monkeypatch.setattr(settings, "compliance_schedule_enabled", False)
    reset_compliance_schedule_kill_switch_cache()
    response = await client.get("/api/v1/compliance-schedule/stats", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_kill_switch_engaged_returns_404(
    client: AsyncClient,
    auth_headers: dict,
    enable_compliance_schedule,
    monkeypatch,
):
    async def _closed() -> bool:
        return False

    monkeypatch.setattr(
        "src.api.routes.compliance_schedule.compliance_schedule_is_open",
        _closed,
    )
    response = await client.get("/api/v1/compliance-schedule/stats", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_forbidden_without_permission(client: AsyncClient, enable_compliance_schedule):
    headers = _cs_headers("incident:read")
    response = await client.get("/api/v1/compliance-schedule/stats", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_happy_path_activate_complete(
    client: AsyncClient,
    enable_compliance_schedule,
    seeded_template,
    superuser_auth_headers: dict,
):
    headers = superuser_auth_headers

    catalogue = await client.get("/api/v1/compliance-schedule/catalogue", headers=headers)
    assert catalogue.status_code == 200
    keys = {item["template_key"] for item in catalogue.json()["items"]}
    assert "wave1-fra" in keys

    activate = await client.post(
        "/api/v1/compliance-schedule/catalogue/wave1-fra/activate",
        headers=headers,
        json={"next_due_date": "2026-04-01"},
    )
    assert activate.status_code == 201, activate.text
    requirement = activate.json()
    assert requirement["reference_number"].startswith("CSR-")
    assert requirement["next_due_date"] == "2026-04-01"
    assert requirement["status"] in {"current", "due_soon", "overdue"}
    assert "Expired" not in str(requirement)

    req_id = requirement["id"]
    complete = await client.post(
        f"/api/v1/compliance-schedule/requirements/{req_id}/records",
        headers=headers,
        json={
            "completed_at": datetime(2026, 4, 2, tzinfo=timezone.utc).isoformat(),
            "check_passed": True,
            "notes": "Completed on site",
        },
    )
    assert complete.status_code == 201, complete.text
    record = complete.json()
    assert record["reference_number"].startswith("CRC-")
    assert record["outcome"] == "completed"
    assert record["due_date"] == "2026-04-01"

    detail = await client.get(
        f"/api/v1/compliance-schedule/requirements/{req_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    updated = detail.json()
    assert updated["next_due_date"] == "2027-04-01"
    assert updated["last_completed_at"] is not None

    stats = await client.get("/api/v1/compliance-schedule/stats", headers=headers)
    assert stats.status_code == 200
    body = stats.json()
    assert body["total_active"] >= 1
    assert set(body) >= {"total_active", "current", "due_soon", "overdue"}


@pytest.mark.asyncio
async def test_activate_empty_catalogue_key_404(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
):
    response = await client.post(
        "/api/v1/compliance-schedule/catalogue/no-such-template/activate",
        headers=superuser_auth_headers,
        json={},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_with_due_overrides(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
):
    response = await client.post(
        "/api/v1/compliance-schedule/requirements",
        headers=superuser_auth_headers,
        json={
            "title": "Custom LEV",
            "taxonomy_id": "HS-02",
            "frequency_months": 14,
            "anchor": "completion",
            "next_due_date": "2026-06-15",
            "last_completed_at": "2025-04-15T10:00:00Z",
            "statutory": True,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["next_due_date"] == "2026-06-15"
    assert body["last_completed_at"] is not None
    assert body["anchor"] == "completion"
