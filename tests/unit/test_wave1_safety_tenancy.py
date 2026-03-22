import types
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import HTTPException
from starlette.responses import Response

from src.api.routes.documents import list_documents, upload_document
from src.api.routes.employee_portal import get_default_portal_tenant_id
from src.api.routes.telemetry import WebVitalsPayload, receive_web_vitals
from src.core.middleware import RequestStateMiddleware
from src.core.security import create_access_token
from src.core.uat_safety import _get_user_id_from_request
from src.domain.models.user import User


class _FakeUploadFile:
    def __init__(self, filename: str, content: bytes, content_type: str):
        self.filename = filename
        self._content = content
        self.content_type = content_type

    async def read(self) -> bytes:
        return self._content


class _FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return list(self._values)


class _FakeExecuteResult:
    def __init__(self, values=None):
        self._values = values or []

    def scalars(self):
        return _FakeScalarResult(self._values)


@pytest.mark.asyncio
async def test_request_state_middleware_sets_user_id_from_bearer_token():
    middleware = RequestStateMiddleware(app=lambda scope, receive, send: None)
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {create_access_token(subject='42')}"}
    request.state = types.SimpleNamespace()

    async def call_next(_request):
        return Response("ok")

    await middleware.dispatch(request, call_next)

    assert request.state.user_id == "42"
    assert request.state.request_id is not None


def test_uat_safety_ignores_spoofed_x_user_id_header():
    request = MagicMock()
    request.state = types.SimpleNamespace()
    request.headers = {"X-User-ID": "spoofed-user"}

    assert _get_user_id_from_request(request) is None


def test_has_permission_requires_exact_permission_match():
    user_like = types.SimpleNamespace(
        is_superuser=False,
        roles=[types.SimpleNamespace(permissions='["incident.read"]')],
    )

    assert User.has_permission(user_like, "incident.read") is True
    assert User.has_permission(user_like, "incident.re") is False


def test_get_default_portal_tenant_id_fails_closed_when_missing(monkeypatch):
    monkeypatch.setattr("src.api.routes.employee_portal.settings.default_tenant_id", None)

    with pytest.raises(HTTPException) as exc:
        get_default_portal_tenant_id()

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_upload_document_sets_document_tenant(monkeypatch):
    added = []

    async def refresh(doc):
        doc.id = 1
        doc.reference_number = "DOC-0001"

    db = types.SimpleNamespace(
        add=lambda obj: added.append(obj),
        commit=AsyncMock(),
        refresh=AsyncMock(side_effect=refresh),
    )
    current_user = types.SimpleNamespace(id=7, tenant_id=81, is_superuser=False)

    response = await upload_document(
        db,
        current_user,
        _FakeUploadFile("audit-report.pdf", b"%PDF-1.4 test", "application/pdf"),
        title="Audit report",
        description="Quarterly report",
    )

    document = added[0]
    assert document.tenant_id == 81
    assert document.created_by_id == 7
    assert response.id == 1


@pytest.mark.asyncio
async def test_list_documents_scopes_queries_to_current_tenant():
    executed = []

    async def execute(statement):
        executed.append(statement)
        return _FakeExecuteResult([])

    db = types.SimpleNamespace(execute=AsyncMock(side_effect=execute), scalar=AsyncMock(return_value=0))
    current_user = types.SimpleNamespace(id=5, tenant_id=12, is_superuser=False)

    response = await list_documents(db, current_user, 1, 20)

    assert response.total == 0
    assert "documents.tenant_id" in str(executed[0])


@pytest.mark.asyncio
async def test_receive_web_vitals_logs_bounded_payload_without_extra_fields(monkeypatch):
    logger = Mock()
    monkeypatch.setattr("src.api.routes.telemetry.logger", logger)

    payload = WebVitalsPayload(
        name="LCP",
        value=123.4,
        delta=5.0,
        id="metric-1",
        rating="good",
        navigationType="navigate",
        timestamp="2026-03-22T10:00:00Z",
    )

    response = await receive_web_vitals(payload)

    assert response == {"status": "ok"}
    logger.info.assert_called_once()
    logged_payload = logger.info.call_args.kwargs["extra"]["payload"]
    assert logged_payload["name"] == "LCP"
    assert "url" not in logged_payload
