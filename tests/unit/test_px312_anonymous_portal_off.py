"""PX-312: anonymous portal submissions are hard-off at the API.

Decision: do not build anonymous reporting. POST /portal/reports/ with
``is_anonymous: true`` must 422 with VALIDATION_ERROR before any DB write.
There is no FEATURE_DISABLED code in ErrorCode; VALIDATION_ERROR is the
matching existing code for a refused request body.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import get_optional_current_user
from src.api.middleware.error_handler import register_exception_handlers
from src.api.routes.employee_portal import router
from src.infrastructure.database import get_db

PORTAL_REPORTS_PATH = "/api/v1/portal/reports/"


class _WriteGuardSession:
    """Fails loudly if submit_quick_report reaches persistence."""

    def add(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("PX-312: anonymous submit must not write to the database")

    async def execute(self, *_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("PX-312: anonymous submit must not query the database")

    async def flush(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("PX-312: anonymous submit must not flush")

    async def commit(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("PX-312: anonymous submit must not commit")


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1/portal")

    async def _db():
        yield _WriteGuardSession()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_optional_current_user] = lambda: None
    return TestClient(app)


def test_anonymous_portal_submit_returns_422_before_db_write(client: TestClient):
    response = client.post(
        PORTAL_REPORTS_PATH,
        json={
            "report_type": "incident",
            "title": "PX-312 anonymous hard-off",
            "description": "Must be rejected before any persistence",
            "severity": "low",
            "is_anonymous": True,
        },
    )

    assert response.status_code == 422
    body = response.json()
    error = body.get("error") or body.get("detail") or body
    if isinstance(error, dict) and "code" in error:
        code = error["code"]
        message = error.get("message", "")
    elif isinstance(error, dict) and isinstance(error.get("detail"), dict):
        code = error["detail"].get("code")
        message = error["detail"].get("message", "")
    else:
        code = None
        message = str(error)

    assert code == "VALIDATION_ERROR"
    assert "anonymous" in message.lower()
