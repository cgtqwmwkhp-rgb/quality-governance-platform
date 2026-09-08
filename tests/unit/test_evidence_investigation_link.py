"""Unit tests for late-binding source evidence onto an open investigation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.evidence_asset import EvidenceSourceModule
from src.domain.models.investigation import AssignedEntityType
from src.domain.services.evidence_investigation_link import (
    assigned_entity_type_for_evidence_module,
    resolve_linked_investigation_id,
)


class TestAssignedEntityTypeForEvidenceModule:
    def test_maps_the_four_source_registers(self) -> None:
        assert (
            assigned_entity_type_for_evidence_module(EvidenceSourceModule.INCIDENT)
            == AssignedEntityType.REPORTING_INCIDENT
        )
        assert assigned_entity_type_for_evidence_module("near_miss") == AssignedEntityType.NEAR_MISS
        assert (
            assigned_entity_type_for_evidence_module("road_traffic_collision")
            == AssignedEntityType.ROAD_TRAFFIC_COLLISION
        )
        assert assigned_entity_type_for_evidence_module("complaint") == AssignedEntityType.COMPLAINT

    def test_does_not_invent_a_link_for_investigation_or_audit_uploads(self) -> None:
        assert assigned_entity_type_for_evidence_module(EvidenceSourceModule.INVESTIGATION) is None
        assert assigned_entity_type_for_evidence_module("audit") is None
        assert assigned_entity_type_for_evidence_module("") is None


class TestResolveLinkedInvestigationId:
    @pytest.mark.asyncio
    async def test_returns_the_matching_investigation_id(self) -> None:
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.first.return_value = 88
        db.execute.return_value = result

        found = await resolve_linked_investigation_id(
            db,
            source_module="incident",
            source_id=12,
            tenant_id=3,
        )

        assert found == 88
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_the_module_is_not_a_source_register(self) -> None:
        db = AsyncMock()

        found = await resolve_linked_investigation_id(
            db,
            source_module="investigation",
            source_id=12,
            tenant_id=3,
        )

        assert found is None
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_source_id_is_not_an_int(self) -> None:
        db = AsyncMock()

        found = await resolve_linked_investigation_id(
            db,
            source_module="incident",
            source_id="not-an-id",
            tenant_id=3,
        )

        assert found is None
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_refuses_to_guess_when_tenant_id_is_missing(self) -> None:
        db = AsyncMock()

        found = await resolve_linked_investigation_id(
            db,
            source_module="incident",
            source_id=12,
            tenant_id=None,
        )

        assert found is None
        db.execute.assert_not_called()
