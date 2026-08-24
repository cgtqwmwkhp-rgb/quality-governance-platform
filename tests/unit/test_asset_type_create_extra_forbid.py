"""B-10: AssetTypeCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.asset import AssetTypeCreate


def test_asset_type_create_accepts_known_fields() -> None:
    m = AssetTypeCreate(
        category="lifting",
        name="MEWP",
        description="Mobile elevating work platform",
        icon="crane",
        is_active=True,
        force=True,
    )
    assert m.name == "MEWP"
    assert m.force is True


def test_asset_type_create_defaults() -> None:
    m = AssetTypeCreate(category="power", name="Generator")
    assert m.description is None
    assert m.is_active is True
    assert m.force is False


def test_asset_type_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AssetTypeCreate(
            category="power",
            name="Generator",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
