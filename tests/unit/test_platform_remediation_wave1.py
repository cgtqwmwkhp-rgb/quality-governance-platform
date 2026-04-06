import io
import types

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from starlette.datastructures import Headers, UploadFile

from src.api.routes.evidence_assets import list_evidence_assets, upload_evidence_asset
from src.domain.exceptions import ValidationError
from src.domain.models.investigation import AssignedEntityType
from src.domain.services.audit_service import AuditService
from src.domain.services.evidence_service import EvidenceService
from src.domain.services.investigation_service import InvestigationService as DomainInvestigationService
from src.infrastructure.storage import StorageDependencyError


@pytest.mark.asyncio
async def test_evidence_upload_returns_safe_error_when_storage_dependency_is_unavailable(monkeypatch):
    async def _validate_source_exists(*args, **kwargs):
        return True

    class _FailingStorage:
        async def upload(self, **kwargs):
            raise StorageDependencyError("container missing")

    monkeypatch.setattr("src.api.routes.evidence_assets.validate_source_exists", _validate_source_exists)
    monkeypatch.setattr("src.infrastructure.storage.storage_service", lambda: _FailingStorage())

    file = UploadFile(
        file=io.BytesIO(b"jpeg-bytes"),
        filename="scene.jpg",
        headers=Headers({"content-type": "image/jpeg"}),
    )

    with pytest.raises(HTTPException) as exc_info:
        await upload_evidence_asset(
            db=types.SimpleNamespace(),
            current_user=types.SimpleNamespace(id=42, tenant_id=1),
            file=file,
            source_module="road_traffic_collision",
            source_id=7,
            asset_type=None,
            title=None,
            description=None,
            captured_at=None,
            captured_by_role=None,
            latitude=None,
            longitude=None,
            location_description=None,
            visibility="internal_customer",
            contains_pii=False,
            redaction_required=False,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error_code"] == "STORAGE_DEPENDENCY_UNAVAILABLE"
    assert "temporarily unavailable" in exc_info.value.detail["message"].lower()


@pytest.mark.asyncio
async def test_evidence_upload_returns_safe_error_when_metadata_persistence_fails(monkeypatch):
    async def _validate_source_exists(*args, **kwargs):
        return True

    cleanup_calls: list[str] = []

    class _Storage:
        async def upload(self, **kwargs):
            return "ok"

        async def delete(self, storage_key: str):
            cleanup_calls.append(storage_key)
            return True

    class _FailingDb:
        def add(self, _value):
            return None

        async def commit(self):
            raise SQLAlchemyError("insert failed")

        async def rollback(self):
            return None

        async def refresh(self, _value):
            return None

    monkeypatch.setattr("src.api.routes.evidence_assets.validate_source_exists", _validate_source_exists)
    monkeypatch.setattr("src.infrastructure.storage.storage_service", lambda: _Storage())

    file = UploadFile(
        file=io.BytesIO(b"jpeg-bytes"),
        filename="scene.jpg",
        headers=Headers({"content-type": "image/jpeg"}),
    )

    with pytest.raises(HTTPException) as exc_info:
        await upload_evidence_asset(
            db=_FailingDb(),
            current_user=types.SimpleNamespace(id=42, tenant_id=1),
            file=file,
            source_module="road_traffic_collision",
            source_id=7,
            asset_type=None,
            title=None,
            description=None,
            captured_at=None,
            captured_by_role=None,
            latitude=None,
            longitude=None,
            location_description=None,
            visibility="internal_customer",
            contains_pii=False,
            redaction_required=False,
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail["error_code"] == "EVIDENCE_METADATA_PERSIST_FAILED"
    assert cleanup_calls


@pytest.mark.asyncio
async def test_evidence_upload_persists_source_id_as_string(monkeypatch):
    async def _validate_source_exists(*args, **kwargs):
        return True

    class _Storage:
        async def upload(self, **kwargs):
            return "ok"

    class _RecordingDb:
        def __init__(self):
            self.added = []

        def add(self, value):
            self.added.append(value)

        async def commit(self):
            return None

        async def rollback(self):
            return None

        async def refresh(self, value):
            value.id = 101
            return None

    monkeypatch.setattr("src.api.routes.evidence_assets.validate_source_exists", _validate_source_exists)
    monkeypatch.setattr("src.infrastructure.storage.storage_service", lambda: _Storage())

    file = UploadFile(
        file=io.BytesIO(b"jpeg-bytes"),
        filename="scene.jpg",
        headers=Headers({"content-type": "image/jpeg"}),
    )
    db = _RecordingDb()

    response = await upload_evidence_asset(
        db=db,
        current_user=types.SimpleNamespace(id=42, tenant_id=1),
        file=file,
        source_module="road_traffic_collision",
        source_id=7,
        asset_type=None,
        title=None,
        description=None,
        captured_at=None,
        captured_by_role=None,
        latitude=None,
        longitude=None,
        location_description=None,
        visibility="internal_customer",
        contains_pii=False,
        redaction_required=False,
    )

    assert db.added[0].source_id == "7"
    assert response.id == 101


@pytest.mark.asyncio
async def test_evidence_list_filters_source_id_as_string():
    class _Result:
        def scalars(self):
            return self

        def all(self):
            return []

    class _RecordingDb:
        def __init__(self):
            self.executed_query = None

        async def scalar(self, _query):
            return 0

        async def execute(self, query):
            self.executed_query = query
            return _Result()

    db = _RecordingDb()

    response = await list_evidence_assets(
        db=db,
        current_user=types.SimpleNamespace(id=42, tenant_id=1),
        source_module=None,
        source_id=42,
        asset_type=None,
        linked_investigation_id=None,
        include_deleted=False,
        page=1,
        page_size=20,
    )

    compiled = db.executed_query.compile()
    assert "42" in compiled.params.values()
    assert response.items == []


@pytest.mark.asyncio
async def test_evidence_service_upload_persists_source_id_as_string(monkeypatch):
    async def _validate_source_exists(*args, **kwargs):
        return True

    async def _invalidate_tenant_cache(*args, **kwargs):
        return None

    class _Storage:
        async def upload(self, **kwargs):
            return "ok"

    class _RecordingDb:
        def __init__(self):
            self.added = []

        def add(self, value):
            self.added.append(value)

        async def commit(self):
            return None

        async def refresh(self, _value):
            return None

    monkeypatch.setattr(EvidenceService, "validate_source_exists", _validate_source_exists)
    monkeypatch.setattr("src.infrastructure.storage.storage_service", lambda: _Storage())
    monkeypatch.setattr("src.domain.services.evidence_service.invalidate_tenant_cache", _invalidate_tenant_cache)
    monkeypatch.setattr("src.domain.services.evidence_service.track_metric", lambda *args, **kwargs: None)

    db = _RecordingDb()
    service = EvidenceService(db)

    asset = await service.upload(
        file_content=b"jpeg-bytes",
        filename="scene.jpg",
        content_type="image/jpeg",
        source_module="road_traffic_collision",
        source_id=7,
        user_id=42,
        tenant_id=None,
    )

    assert db.added[0].source_id == "7"
    assert asset.source_id == "7"


@pytest.mark.asyncio
async def test_evidence_service_list_filters_source_id_as_string(monkeypatch):
    captured = {}

    async def _paginate(_db, query, _params):
        captured["query"] = query
        return []

    monkeypatch.setattr("src.domain.services.evidence_service.paginate", _paginate)

    service = EvidenceService(types.SimpleNamespace())

    result = await service.list_assets(
        tenant_id=None,
        params=types.SimpleNamespace(),
        source_module=None,
        source_id=42,
    )

    compiled = captured["query"].compile()
    assert "42" in compiled.params.values()
    assert result == []


@pytest.mark.asyncio
async def test_domain_investigation_service_filters_evidence_source_id_as_string():
    class _Result:
        def scalars(self):
            return self

        def all(self):
            return []

    class _RecordingDb:
        def __init__(self):
            self.executed_query = None

        async def execute(self, query):
            self.executed_query = query
            return _Result()

    db = _RecordingDb()

    result = await DomainInvestigationService.get_source_evidence_assets(
        db=db,
        source_type=AssignedEntityType.ROAD_TRAFFIC_COLLISION,
        source_id=42,
    )

    compiled = db.executed_query.compile()
    assert "42" in compiled.params.values()
    assert result == []


def test_publish_validation_requires_complete_choice_question_options():
    question = types.SimpleNamespace(
        question_text="Select the outcome",
        weight=1,
        question_type="radio",
        options_json=[{"label": "Pass", "value": "pass"}],
    )
    section = types.SimpleNamespace(title="Inspection", questions=[question])
    template = types.SimpleNamespace(name="Vehicle Inspection", sections=[section], questions=[question])

    with pytest.raises(ValidationError, match="at least two answer options"):
        AuditService._validate_publishable_template(template)
