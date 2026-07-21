"""Wave C1 UAT API fixes — search mount, evidence list, feature flags, signatures, policy ack."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import ProgrammingError

from src.api.routes.evidence_assets import _evidence_asset_response, list_evidence_assets
from src.api.routes.feature_flags import list_feature_flags
from src.api.routes.global_search import router as search_router
from src.api.routes.policy_acknowledgment import get_compliance_dashboard, get_my_pending_acknowledgments
from src.api.routes.signatures import _format_request
from src.api.schemas.evidence_asset import EvidenceAssetResponse
from src.domain.models.evidence_asset import (
    EvidenceAssetType,
    EvidenceRetentionPolicy,
    EvidenceSourceModule,
    EvidenceVisibility,
)


def test_global_search_dual_mount_without_trailing_slash():
    paths = {getattr(r, "path", None) for r in search_router.routes}
    assert "" in paths
    assert "/" in paths


def test_evidence_asset_response_accepts_action_key_source_id():
    asset = SimpleNamespace(
        id=1,
        storage_key="k",
        original_filename="f.png",
        content_type="image/png",
        file_size_bytes=100,
        checksum_sha256="abc",
        asset_type=EvidenceAssetType.PHOTO,
        source_module=EvidenceSourceModule.ACTION,
        source_id="capa:12",
        linked_investigation_id=None,
        title=None,
        description=None,
        captured_at=None,
        captured_by_role=None,
        latitude=None,
        longitude=None,
        location_description=None,
        render_hint=None,
        thumbnail_storage_key=None,
        metadata_json=None,
        visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
        contains_pii=False,
        redaction_required=False,
        retention_policy=EvidenceRetentionPolicy.STANDARD,
        retention_expires_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by_id=1,
        updated_by_id=1,
    )
    response = _evidence_asset_response(asset)
    assert response.source_id == "capa:12"
    assert isinstance(response, EvidenceAssetResponse)


@pytest.mark.asyncio
async def test_list_evidence_assets_skips_invalid_rows_instead_of_500():
    good = SimpleNamespace(
        id=1,
        storage_key="k",
        original_filename="f.png",
        content_type="image/png",
        file_size_bytes=100,
        checksum_sha256="abc",
        asset_type=EvidenceAssetType.PHOTO,
        source_module=EvidenceSourceModule.INCIDENT,
        source_id="7",
        linked_investigation_id=None,
        title=None,
        description=None,
        captured_at=None,
        captured_by_role=None,
        latitude=None,
        longitude=None,
        location_description=None,
        render_hint=None,
        thumbnail_storage_key=None,
        metadata_json=None,
        visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
        contains_pii=False,
        redaction_required=False,
        retention_policy=EvidenceRetentionPolicy.STANDARD,
        retention_expires_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by_id=1,
        updated_by_id=1,
    )
    bad = SimpleNamespace(id=2)

    class _Result:
        def scalars(self):
            return self

        def all(self):
            return [good, bad]

    class _Db:
        async def scalar(self, _query):
            return 2

        async def execute(self, _query):
            return _Result()

    response = await list_evidence_assets(
        db=_Db(),
        current_user=SimpleNamespace(id=1, tenant_id=1),
        page=1,
        page_size=20,
        source_module=None,
        source_id=None,
        action_key=None,
        asset_type=None,
        linked_investigation_id=None,
        include_deleted=False,
    )
    assert response.total == 2
    assert len(response.items) == 1
    assert response.items[0].source_id == "7"


@pytest.mark.asyncio
async def test_list_feature_flags_fail_soft_on_missing_table():
    db = MagicMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock(side_effect=ProgrammingError("SELECT", {}, Exception("missing table")))

    response = await list_feature_flags(
        db=db,
        current_user=SimpleNamespace(id=1, tenant_id=1),
        skip=0,
        limit=50,
    )
    assert response.items == []
    assert response.total == 0
    db.rollback.assert_awaited_once()


def test_format_request_with_empty_signers():
    request = SimpleNamespace(
        id=1,
        reference_number="SIG-1",
        title="Test",
        description=None,
        document_type="policy",
        workflow_type="sequential",
        status="draft",
        expires_at=None,
        created_at=datetime.now(timezone.utc),
        completed_at=None,
        signers=[],
    )
    payload = _format_request(request)
    assert payload["signers"] == []


@pytest.mark.asyncio
async def test_policy_ack_dashboard_fail_soft_on_missing_table():
    db = MagicMock()
    db.rollback = AsyncMock()

    service = MagicMock()
    service.get_compliance_dashboard = AsyncMock(side_effect=ProgrammingError("SELECT", {}, Exception("missing table")))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "src.api.routes.policy_acknowledgment.PolicyAcknowledgmentService",
            lambda _db: service,
        )
        response = await get_compliance_dashboard(
            db=db,
            current_user=SimpleNamespace(id=1, tenant_id=1),
        )

    assert response.total_assignments == 0
    assert response.completion_rate == 0.0
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_policy_ack_my_pending_fail_soft_on_missing_table():
    db = MagicMock()
    db.rollback = AsyncMock()

    service = MagicMock()
    service.get_user_pending_acknowledgments = AsyncMock(
        side_effect=ProgrammingError("SELECT", {}, Exception("missing table"))
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "src.api.routes.policy_acknowledgment.PolicyAcknowledgmentService",
            lambda _db: service,
        )
        response = await get_my_pending_acknowledgments(
            db=db,
            current_user=SimpleNamespace(id=1, tenant_id=1),
        )

    assert response.items == []
    assert response.total == 0
    db.rollback.assert_awaited_once()
