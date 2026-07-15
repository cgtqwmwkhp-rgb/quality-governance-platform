"""Unit tests for CAPA → AuditFinding closure bridge (CUJ-AUDIT-CAPA-CLOSURE-BRIDGE)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import StateTransitionError
from src.domain.models.audit import FindingStatus
from src.domain.models.capa import CAPASource, CAPAStatus
from src.domain.services.audit_service import AuditService
from src.domain.services.capa_service import CAPAService


def _fake_capa(**overrides):
    defaults = {
        "id": 11,
        "reference_number": "CAPA-2026-0011",
        "title": "Fix PPE",
        "status": CAPAStatus.VERIFICATION,
        "tenant_id": 1,
        "source_type": CAPASource.AUDIT_FINDING,
        "source_id": 42,
        "created_by_id": 5,
        "assigned_to_id": 7,
        "completed_at": datetime.now(timezone.utc),
        "verified_at": None,
        "verified_by_id": None,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _fake_finding(**overrides):
    defaults = {
        "id": 42,
        "reference_number": "FND-2026-0001",
        "title": "Missing PPE",
        "status": FindingStatus.OPEN,
        "tenant_id": 1,
        "run_id": 9,
        "created_by_id": 5,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "risk_ids_json": [],
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _fake_run(**overrides):
    defaults = {
        "id": 9,
        "reference_number": "AUD-2026-0001",
        "tenant_id": 1,
        "assigned_to_id": 3,
        "created_by_id": 5,
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class TestHonestChainStatus:
    def test_closed_when_aligned(self):
        assert (
            AuditService._honest_chain_status(
                FindingStatus.CLOSED.value,
                [{"status": CAPAStatus.CLOSED.value}],
            )
            == "closed"
        )

    def test_desynced_when_capa_closed_finding_open(self):
        assert (
            AuditService._honest_chain_status(
                FindingStatus.OPEN.value,
                [{"status": CAPAStatus.CLOSED.value}],
            )
            == "desynced_capa_closed_finding_open"
        )

    def test_no_capa_open(self):
        assert AuditService._honest_chain_status(FindingStatus.OPEN.value, []) == "finding_open_no_capa"

    def test_desynced_when_finding_closed_capa_open(self):
        assert (
            AuditService._honest_chain_status(
                FindingStatus.CLOSED.value,
                [{"status": CAPAStatus.OPEN.value}],
            )
            == "desynced_finding_closed_capa_open"
        )


class TestUpdateFindingCloseGate:
    @pytest.mark.asyncio
    async def test_update_finding_rejects_close_with_open_capa(self):
        finding = _fake_finding(status=FindingStatus.OPEN)
        open_capa = _fake_capa(id=11, status=CAPAStatus.OPEN)

        db = AsyncMock()
        siblings = MagicMock()
        siblings.scalars.return_value.all.return_value = [open_capa]
        db.execute.return_value = siblings

        svc = AuditService(db)
        svc._get_entity = AsyncMock(return_value=finding)

        with pytest.raises(StateTransitionError, match="linked CAPA actions remain open"):
            await svc.update_finding(
                finding.id,
                {"status": FindingStatus.CLOSED.value},
                tenant_id=1,
                actor_user_id=5,
            )

    @pytest.mark.asyncio
    @patch("src.domain.services.audit_service.invalidate_tenant_cache", new_callable=AsyncMock)
    async def test_update_finding_allows_close_when_all_capas_closed(self, _cache):
        finding = _fake_finding(status=FindingStatus.PENDING_VERIFICATION)
        closed_capa = _fake_capa(id=11, status=CAPAStatus.CLOSED)
        run = _fake_run()

        db = AsyncMock()
        capa_result = MagicMock()
        capa_result.scalars.return_value.all.return_value = [closed_capa]
        db.execute.return_value = capa_result

        svc = AuditService(db)
        svc._get_entity = AsyncMock(side_effect=[finding, run])
        svc._ensure_action_for_finding = AsyncMock(return_value=closed_capa)
        svc._ensure_risk_for_finding = AsyncMock(return_value=None)

        updated = await svc.update_finding(
            finding.id,
            {"status": FindingStatus.CLOSED.value},
            tenant_id=1,
            actor_user_id=5,
        )

        assert updated.status == FindingStatus.CLOSED


class TestApplyCapaClosureBridge:
    @pytest.mark.asyncio
    @patch("src.domain.services.audit_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.audit_service.track_metric")
    @patch("src.domain.services.audit_service.record_audit_event", new_callable=AsyncMock)
    async def test_verification_advances_finding(self, _audit, _metric, _cache):
        finding = _fake_finding(status=FindingStatus.OPEN)
        run = _fake_run()
        capa = _fake_capa(status=CAPAStatus.VERIFICATION)

        db = AsyncMock()
        siblings = MagicMock()
        siblings.scalars.return_value.all.return_value = [capa]
        db.execute.return_value = siblings

        svc = AuditService(db)
        svc._get_entity = AsyncMock(side_effect=[finding, run])

        result = await svc.apply_capa_closure_bridge(capa, actor_user_id=5, tenant_id=1)

        assert result["changed"] is True
        assert result["to_status"] == FindingStatus.PENDING_VERIFICATION.value
        assert finding.status == FindingStatus.PENDING_VERIFICATION
        assert result["notify_user_id"] == 3

    @pytest.mark.asyncio
    @patch("src.domain.services.audit_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.audit_service.track_metric")
    @patch("src.domain.services.audit_service.record_audit_event", new_callable=AsyncMock)
    async def test_closed_advances_finding(self, _audit, _metric, _cache):
        finding = _fake_finding(status=FindingStatus.PENDING_VERIFICATION)
        run = _fake_run()
        capa = _fake_capa(status=CAPAStatus.CLOSED)

        db = AsyncMock()
        siblings = MagicMock()
        siblings.scalars.return_value.all.return_value = [capa]
        db.execute.return_value = siblings

        svc = AuditService(db)
        svc._get_entity = AsyncMock(side_effect=[finding, run])

        result = await svc.apply_capa_closure_bridge(capa, actor_user_id=5, tenant_id=1)

        assert result["changed"] is True
        assert result["to_status"] == FindingStatus.CLOSED.value
        assert finding.status == FindingStatus.CLOSED

    @pytest.mark.asyncio
    async def test_idempotent_when_already_synced(self):
        finding = _fake_finding(status=FindingStatus.CLOSED)
        capa = _fake_capa(status=CAPAStatus.CLOSED)

        db = AsyncMock()
        siblings = MagicMock()
        siblings.scalars.return_value.all.return_value = [capa]
        db.execute.return_value = siblings

        svc = AuditService(db)
        svc._get_entity = AsyncMock(return_value=finding)

        result = await svc.apply_capa_closure_bridge(capa, actor_user_id=5, tenant_id=1)

        assert result["bridged"] is True
        assert result["changed"] is False
        assert result["skipped_reason"] == "already_synced"

    @pytest.mark.asyncio
    async def test_skips_non_audit_finding_source(self):
        capa = _fake_capa(source_type="incident", source_id=99, status=CAPAStatus.CLOSED)
        svc = AuditService(AsyncMock())
        result = await svc.apply_capa_closure_bridge(capa, actor_user_id=5, tenant_id=1)
        assert result["bridged"] is False
        assert result["skipped_reason"] == "not_audit_finding_source"

    @pytest.mark.asyncio
    async def test_does_not_downgrade_closed_on_verification(self):
        finding = _fake_finding(status=FindingStatus.CLOSED)
        capa = _fake_capa(status=CAPAStatus.VERIFICATION)

        db = AsyncMock()
        siblings = MagicMock()
        siblings.scalars.return_value.all.return_value = [capa]
        db.execute.return_value = siblings

        svc = AuditService(db)
        svc._get_entity = AsyncMock(return_value=finding)

        result = await svc.apply_capa_closure_bridge(capa, actor_user_id=5, tenant_id=1)
        assert result["changed"] is False
        assert result["skipped_reason"] == "finding_already_closed"
        assert finding.status == FindingStatus.CLOSED

    @pytest.mark.asyncio
    async def test_sibling_blocker_prevents_close(self):
        finding = _fake_finding(status=FindingStatus.PENDING_VERIFICATION)
        capa = _fake_capa(id=11, status=CAPAStatus.CLOSED)
        sibling = _fake_capa(id=12, status=CAPAStatus.IN_PROGRESS)

        db = AsyncMock()
        siblings = MagicMock()
        siblings.scalars.return_value.all.return_value = [capa, sibling]
        db.execute.return_value = siblings

        svc = AuditService(db)
        svc._get_entity = AsyncMock(return_value=finding)

        result = await svc.apply_capa_closure_bridge(capa, actor_user_id=5, tenant_id=1)
        assert result["changed"] is False
        assert result["skipped_reason"] == "sibling_capa_not_closed"
        assert finding.status == FindingStatus.PENDING_VERIFICATION


class TestCapaTransitionInvokesBridge:
    @pytest.mark.asyncio
    @patch("src.domain.services.capa_service.track_metric")
    @patch("src.domain.services.capa_service.record_audit_event", new_callable=AsyncMock)
    async def test_transition_closed_calls_bridge_and_notify(self, _audit, _metric):
        capa = _fake_capa(status=CAPAStatus.VERIFICATION)
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = capa
        db.execute.return_value = result_mock

        bridge_result = {"changed": True, "notify_user_id": 3, "finding_id": 42}
        with patch("src.domain.services.audit_service.AuditService") as mock_audit_cls:
            mock_svc = MagicMock()
            mock_svc.apply_capa_closure_bridge = AsyncMock(return_value=bridge_result)
            mock_svc.notify_capa_closure_bridge = AsyncMock()
            mock_audit_cls.return_value = mock_svc

            svc = CAPAService(db)
            await svc.transition_status(11, CAPAStatus.CLOSED, user_id=5, tenant_id=1)

            mock_svc.apply_capa_closure_bridge.assert_awaited_once()
            db.commit.assert_awaited()
            mock_svc.notify_capa_closure_bridge.assert_awaited_once()


class TestNotifyBridge:
    @pytest.mark.asyncio
    async def test_notify_skipped_when_unchanged(self):
        svc = AuditService(AsyncMock())
        await svc.notify_capa_closure_bridge(
            bridge_result={"changed": False},
            capa=_fake_capa(),
            actor_user_id=1,
        )

    @pytest.mark.asyncio
    async def test_notify_calls_create_status(self):
        db = AsyncMock()
        svc = AuditService(db)
        with patch("src.domain.services.notification_service.NotificationService") as mock_cls:
            mock_notif = MagicMock()
            mock_notif.create_status = AsyncMock()
            mock_cls.return_value = mock_notif

            await svc.notify_capa_closure_bridge(
                bridge_result={
                    "changed": True,
                    "notify_user_id": 3,
                    "finding_id": 42,
                    "run_id": 9,
                    "from_status": "pending_verification",
                    "to_status": "closed",
                },
                capa=_fake_capa(status=CAPAStatus.CLOSED),
                actor_user_id=5,
            )
            mock_notif.create_status.assert_awaited_once()
            kwargs = mock_notif.create_status.await_args.kwargs
            assert kwargs["user_id"] == 3
            assert kwargs["to_status"] == "closed"
