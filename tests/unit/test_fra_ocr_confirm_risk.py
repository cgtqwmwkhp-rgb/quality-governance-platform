"""Unit tests for FRA OCR confirm → risk proposal (slice 6)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import ValidationError
from src.domain.services.compliance_schedule_fra_ocr_service import ComplianceScheduleFraOcrService


@pytest.mark.asyncio
async def test_create_risk_from_confirm_requires_operator_scores() -> None:
    db = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)
    draft = SimpleNamespace(id=7)
    requirement = SimpleNamespace(
        id=10,
        reference_number="CSR-1",
        title="FRA",
        owner_id=3,
        tenant_id=1,
    )

    with pytest.raises(ValidationError):
        await service._create_risk_from_confirm(
            draft=draft,
            requirement=requirement,
            risk={"title": "Missing scores"},
            user_id=42,
            tenant_id=1,
        )


@pytest.mark.asyncio
async def test_create_risk_from_confirm_rejects_out_of_range_scores() -> None:
    db = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)
    draft = SimpleNamespace(id=7)
    requirement = SimpleNamespace(
        id=10,
        reference_number="CSR-1",
        title="FRA",
        owner_id=3,
        tenant_id=1,
    )

    with pytest.raises(ValidationError):
        await service._create_risk_from_confirm(
            draft=draft,
            requirement=requirement,
            risk={"inherent_likelihood": 0, "inherent_impact": 5},
            user_id=42,
            tenant_id=1,
        )


@pytest.mark.asyncio
async def test_create_risk_from_confirm_calls_risk_service_uncommitted() -> None:
    db = MagicMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=MagicMock(return_value=None)))
    service = ComplianceScheduleFraOcrService(db)
    draft = SimpleNamespace(id=7)
    requirement = SimpleNamespace(
        id=10,
        reference_number="CSR-1",
        title="Fire risk assessment",
        owner_id=3,
        tenant_id=1,
    )
    created = SimpleNamespace(reference="RISK-0001", id=99)
    create_risk = AsyncMock(return_value=created)

    with patch(
        "src.domain.services.compliance_schedule_fra_ocr_service.RiskService",
    ) as risk_service_cls:
        risk_service_cls.return_value = SimpleNamespace(create_risk=create_risk)
        out = await service._create_risk_from_confirm(
            draft=draft,
            requirement=requirement,
            risk={"inherent_likelihood": 2, "inherent_impact": 5, "title": "Escape routes"},
            user_id=42,
            tenant_id=1,
        )

    assert out is created
    assert create_risk.await_args.kwargs["commit"] is False
    data = create_risk.await_args.args[0]
    assert data["inherent_likelihood"] == 2
    assert data["inherent_impact"] == 5
    assert data["source"] == "fra_ocr_draft:7"
    assert data["residual_likelihood"] == 2
    assert data["category"] == "health_safety"


@pytest.mark.asyncio
async def test_create_risk_from_confirm_returns_existing_idempotently() -> None:
    existing = SimpleNamespace(reference="RISK-EXISTING", id=5)
    db = MagicMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=MagicMock(return_value=existing)))
    service = ComplianceScheduleFraOcrService(db)
    draft = SimpleNamespace(id=7)
    requirement = SimpleNamespace(
        id=10,
        reference_number="CSR-1",
        title="FRA",
        owner_id=3,
        tenant_id=1,
    )

    with patch(
        "src.domain.services.compliance_schedule_fra_ocr_service.RiskService",
    ) as risk_service_cls:
        out = await service._create_risk_from_confirm(
            draft=draft,
            requirement=requirement,
            risk={"inherent_likelihood": 3, "inherent_impact": 3},
            user_id=42,
            tenant_id=1,
        )

    assert out is existing
    risk_service_cls.assert_not_called()
