import types
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.api.routes.cross_standard_mappings import MappingCreate, create_mapping


@pytest.mark.asyncio
async def test_create_cross_standard_mapping_sets_tenant_id():
    added = []

    async def refresh(obj):
        obj.id = 1

    execute_result = Mock()
    execute_result.scalars.return_value.first.return_value = None

    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=execute_result),
        add=lambda obj: added.append(obj),
        commit=AsyncMock(),
        refresh=AsyncMock(side_effect=refresh),
    )
    current_user = types.SimpleNamespace(id=11, tenant_id=77)
    primary_standard = types.SimpleNamespace(name="ISO 9001:2015")
    mapped_standard = types.SimpleNamespace(name="ISO 14001:2015")
    primary_clause = types.SimpleNamespace(id=101, clause_number="7.5", title="Documented information")
    mapped_clause = types.SimpleNamespace(id=202, clause_number="7.5", title="Documented information")
    primary_requirement = types.SimpleNamespace(id=1001)
    mapped_requirement = types.SimpleNamespace(id=1002)

    with (
        patch(
            "src.api.routes.cross_standard_mappings._resolve_canonical_clause",
            new=AsyncMock(
                side_effect=[
                    (primary_standard, primary_clause),
                    (mapped_standard, mapped_clause),
                ]
            ),
        ),
        patch(
            "src.api.routes.cross_standard_mappings._get_or_create_ims_requirement",
            new=AsyncMock(side_effect=[primary_requirement, mapped_requirement]),
        ),
    ):
        mapping = await create_mapping(
            MappingCreate(
                primary_standard="ISO 9001:2015",
                primary_clause="7.5",
                mapped_standard="ISO 14001:2015",
                mapped_clause="7.5",
                mapping_type="equivalent",
                mapping_strength=9,
                mapping_notes="Documented information alignment",
                annex_sl_element="Support",
            ),
            db,
            current_user,
        )

    assert added[0].tenant_id == 77
    assert mapping.primary_clause == "7.5"
    assert mapping.mapped_standard == "ISO 14001:2015"


def test_cross_standard_route_is_mounted_in_main_api():
    from src.main import app

    mounted_paths = {route.path for route in app.routes}
    assert any(path.startswith("/api/v1/cross-standard-mappings") for path in mounted_paths)
