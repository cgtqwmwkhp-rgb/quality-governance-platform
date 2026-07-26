"""Unit tests for lookup_defaults_seed (Run021 GROUP 1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.lookup_defaults_seed import seed_lookup_defaults
from src.domain.services.lookup_defaults_seed_data import LOOKUP_DEFAULT_ROWS, SEED_CATEGORIES


@pytest.mark.asyncio
async def test_seed_lookup_defaults_inserts_when_category_empty():
    db = AsyncMock()
    execute_results = iter([MagicMock(scalar_one=lambda: 0) for _ in range(len(SEED_CATEGORIES))])
    db.execute = AsyncMock(side_effect=lambda *_args, **_kwargs: next(execute_results))

    result = await seed_lookup_defaults(db, tenant_id=1)

    assert result.tenants_processed == 1
    assert result.rows_inserted == len(LOOKUP_DEFAULT_ROWS)
    assert len(result.categories_seeded) == len(SEED_CATEGORIES)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_seed_lookup_defaults_skips_populated_categories():
    db = AsyncMock()

    def _count_side_effect(*_args, **_kwargs):
        # workforce_roles populated; others empty
        if not hasattr(_count_side_effect, "calls"):
            _count_side_effect.calls = 0
        _count_side_effect.calls += 1
        value = 3 if _count_side_effect.calls == 1 else 0
        return MagicMock(scalar_one=lambda v=value: v)

    db.execute = AsyncMock(side_effect=_count_side_effect)

    result = await seed_lookup_defaults(db, tenant_id=1)

    assert result.skipped_categories.get("workforce_roles") == 1
    expected_rows = len(LOOKUP_DEFAULT_ROWS) - len(
        [row for row in LOOKUP_DEFAULT_ROWS if row.category == "workforce_roles"]
    )
    assert result.rows_inserted == expected_rows
