"""API-level tests for AM-IMPORT asset CSV endpoints (mocked service)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import get_current_user
from src.api.middleware.error_handler import register_exception_handlers
from src.api.routes import asset_imports
from src.domain.exceptions import ValidationError
from src.domain.services.asset_import_service import ImportCommitResult, ImportValidationReport
from src.infrastructure.database import get_db

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "asset_import"


@pytest.fixture
def api_client() -> TestClient:
    user = SimpleNamespace(
        id=1,
        tenant_id=3,
        email="admin@example.com",
        is_superuser=True,
        has_permission=lambda _perm: True,
    )

    async def _user():
        return user

    async def _db():
        yield MagicMock()

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(asset_imports.router, prefix="/api/v1/asset-imports")
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def test_dry_run_endpoint_returns_report(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    report = ImportValidationReport(
        dry_run=True,
        total_rows=2,
        valid_rows=2,
        error_rows=0,
        errors=[],
        preview=[
            {
                "row": 2,
                "asset_number": "FE-100",
                "name": "X",
                "asset_type_id": 1,
                "status": "active",
            }
        ],
    )

    monkeypatch.setattr(
        asset_imports.AssetImportService,
        "dry_run",
        AsyncMock(return_value=report),
    )

    csv_bytes = (FIXTURES / "valid_tools.csv").read_bytes()
    response = api_client.post(
        "/api/v1/asset-imports/dry-run",
        files={"file": ("tools.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["total_rows"] == 2
    assert body["dry_run"] is True


def test_commit_endpoint_returns_422_on_validation_failure(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        asset_imports.AssetImportService,
        "commit",
        AsyncMock(
            side_effect=ValidationError(
                "CSV import validation failed",
                code="ASSET_IMPORT_VALIDATION_FAILED",
                details={
                    "dry_run": False,
                    "total_rows": 1,
                    "valid_rows": 0,
                    "error_rows": 1,
                    "ok": False,
                    "errors": [
                        {
                            "row": 2,
                            "code": "REQUIRED",
                            "message": "name is required",
                            "field": "name",
                        }
                    ],
                    "preview": [],
                },
            )
        ),
    )

    csv_bytes = (FIXTURES / "invalid_tools.csv").read_bytes()
    response = api_client.post(
        "/api/v1/asset-imports/commit",
        files={"file": ("bad.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "ASSET_IMPORT_VALIDATION_FAILED"
    assert body["error"]["details"]["error_rows"] == 1


def test_commit_endpoint_creates(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    result = ImportCommitResult(
        created_count=2,
        created_asset_ids=[10, 11],
        report=ImportValidationReport(
            dry_run=False,
            total_rows=2,
            valid_rows=2,
            error_rows=0,
            errors=[],
            preview=[],
        ),
    )
    monkeypatch.setattr(
        asset_imports.AssetImportService,
        "commit",
        AsyncMock(return_value=result),
    )

    csv_bytes = (FIXTURES / "valid_tools.csv").read_bytes()
    response = api_client.post(
        "/api/v1/asset-imports/commit",
        files={"file": ("tools.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["created_count"] == 2
    assert body["created_asset_ids"] == [10, 11]


def test_rejects_non_csv(api_client: TestClient):
    response = api_client.post(
        "/api/v1/asset-imports/dry-run",
        files={"file": ("tools.txt", b"not csv", "text/plain")},
    )
    assert response.status_code == 400
