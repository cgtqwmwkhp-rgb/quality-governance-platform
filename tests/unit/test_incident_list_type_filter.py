"""Incident list SQL type filter (register views R2)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.core.pagination import PaginatedResponse, PaginationInput
from src.domain.services.incident_list_filters import (
    CLIENT_ONLY_LIST_PARAMS,
    SERVER_FILTERABLE_PARAMS,
)
from src.domain.services.incident_service import IncidentService


def test_status_and_severity_are_not_server_filterable() -> None:
    assert "type" in SERVER_FILTERABLE_PARAMS
    assert "status" not in SERVER_FILTERABLE_PARAMS
    assert "severity" not in SERVER_FILTERABLE_PARAMS
    assert "status" in CLIENT_ONLY_LIST_PARAMS
    assert "severity" in CLIENT_ONLY_LIST_PARAMS
    assert SERVER_FILTERABLE_PARAMS.isdisjoint(CLIENT_ONLY_LIST_PARAMS)


@pytest.mark.asyncio
async def test_list_incidents_applies_type_in_sql() -> None:
    captured_queries = []

    async def paginate(_db, query, _params):
        captured_queries.append(query)
        return PaginatedResponse(items=[], total=0, page=1, page_size=50, pages=0)

    db = SimpleNamespace(execute=AsyncMock())
    svc = IncidentService(db)

    import src.domain.services.incident_service as incident_service_module

    original_paginate = incident_service_module.paginate
    incident_service_module.paginate = paginate
    try:
        await svc.list_incidents(
            tenant_id=1,
            params=PaginationInput(page=1, page_size=50),
            incident_type="injury",
        )
    finally:
        incident_service_module.paginate = original_paginate

    assert len(captured_queries) == 1
    sql = str(captured_queries[0].compile(compile_kwargs={"literal_binds": True})).lower()
    assert "injury" in sql
    assert "incident_type" in sql


@pytest.mark.asyncio
async def test_unknown_incident_type_query_is_422() -> None:
    from src.api.routes.incidents import list_incidents

    current_user = SimpleNamespace(
        id=7,
        tenant_id=11,
        email="owner@example.com",
        is_superuser=False,
        has_permission=lambda _permission: True,
    )
    with pytest.raises(HTTPException) as exc_info:
        await list_incidents(
            db=SimpleNamespace(),
            current_user=current_user,
            request_id="req-type",
            reporter_email=None,
            owner=None,
            page=1,
            page_size=50,
            incident_type="accident_book",
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["message"] == "Unknown incident type"
