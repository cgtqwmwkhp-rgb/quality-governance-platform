"""B-10: AssetTypeUpdate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.asset import AssetTypeUpdate


def test_asset_type_update_accepts_known_fields() -> None:
    m = AssetTypeUpdate(name="Updated", is_active=False)
    assert m.name == "Updated"
    assert m.is_active is False


def test_asset_type_update_all_optional() -> None:
    m = AssetTypeUpdate()
    assert m.category is None
    assert m.name is None


def test_asset_type_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AssetTypeUpdate(
            name="Updated",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
