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
from src.domain.services.policy_acknowledgment import MeasuredCompliance, UnmeasurableCompliance


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


async def _dashboard_with_service(service) -> object:
    db = MagicMock()
    db.rollback = AsyncMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "src.api.routes.policy_acknowledgment.PolicyAcknowledgmentService",
            lambda _db: service,
        )
        return await get_compliance_dashboard(db=db, current_user=SimpleNamespace(id=1, tenant_id=1))


@pytest.mark.asyncio
async def test_policy_ack_dashboard_reports_unmeasurable_instead_of_zero():
    """C-23 — an absent backing table must not be answered with 0% compliance.

    This replaces ``test_policy_ack_dashboard_fail_soft_on_missing_table``, which
    asserted ``total_assignments == 0`` and ``completion_rate == 0.0`` for exactly
    this condition. That was the fabricated measurement: "0% acknowledged" and
    "acknowledgment could not be measured" are different statements, and only the
    second one was true. The assertions here are strictly stronger — the response
    must carry no number at all, so nothing can be rendered as a percentage.

    ``tests/integration/test_policy_ack_dashboard_honesty.py`` pins the same
    contract against a database with the table genuinely dropped; this test keeps
    the route's mapping covered without a database.
    """
    service = MagicMock()
    service.get_compliance_dashboard = AsyncMock(
        return_value=UnmeasurableCompliance(missing_tables=("policy_acknowledgments",))
    )

    response = await _dashboard_with_service(service)

    assert response.measurement == "unmeasurable"
    assert response.missing_tables == ["policy_acknowledgments"]
    assert not hasattr(response, "metrics")
    numeric = [
        key
        for key, value in response.model_dump().items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    assert numeric == [], f"unmeasurable dashboard offered numbers: {numeric}"


@pytest.mark.asyncio
async def test_policy_ack_dashboard_still_reports_a_real_measurement():
    service = MagicMock()
    service.get_compliance_dashboard = AsyncMock(
        return_value=MeasuredCompliance(
            metrics={
                "total_assignments": 4,
                "completed": 1,
                "pending": 3,
                "overdue": 0,
                "completion_rate": 25.0,
                "overdue_rate": 0.0,
            }
        )
    )

    response = await _dashboard_with_service(service)

    assert response.measurement == "measured"
    assert response.metrics.total_assignments == 4
    assert response.metrics.completion_rate == 25.0


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
