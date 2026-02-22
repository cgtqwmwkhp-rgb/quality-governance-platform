"""Tests for tenant scope utility."""

from unittest.mock import MagicMock
from src.api.utils.tenant import tenant_scope


class TestTenantScope:
    def test_applies_where_clause(self):
        mock_stmt = MagicMock()
        mock_model = MagicMock()
        mock_model.tenant_id = MagicMock()

        result = tenant_scope(mock_stmt, mock_model, 42)
        mock_stmt.where.assert_called_once()
