"""Incident register list search filter (PX-130)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.pagination import PaginatedResponse, PaginationInput
from src.domain.services.incident_service import IncidentService


@pytest.mark.asyncio
async def test_list_incidents_applies_search_filter_on_title_reference_description() -> None:
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
            search="warehouse",
        )
    finally:
        incident_service_module.paginate = original_paginate

    assert len(captured_queries) == 1
    sql = str(captured_queries[0].compile(compile_kwargs={"literal_binds": True})).lower()
    assert "warehouse" in sql
