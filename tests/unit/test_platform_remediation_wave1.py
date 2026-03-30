import io
import types

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from starlette.datastructures import Headers, UploadFile

from src.api.routes.evidence_assets import upload_evidence_asset
from src.domain.exceptions import ValidationError
from src.domain.services.audit_service import AuditService
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
            current_user=types.SimpleNamespace(id=42),
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
            current_user=types.SimpleNamespace(id=42),
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
