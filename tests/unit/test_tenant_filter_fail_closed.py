"""Unit tests for fail-closed tenant filtering and explicit tenant requirements."""

import pytest
from fastapi import HTTPException
from sqlalchemy import Column, Integer, MetaData, Table, false, select

from src.api.utils.tenant import apply_tenant_filter, require_tenant_id

_metadata = MetaData()
_entities = Table(
    "tenant_filter_entities",
    _metadata,
    Column("id", Integer, primary_key=True),
    Column("tenant_id", Integer, nullable=True),
)


class _Model:
    """Stand-in model exposing a tenant_id column like SQLAlchemy mapped classes."""

    tenant_id = _entities.c.tenant_id


def test_apply_tenant_filter_uses_exact_tenant_match_only():
    """Scoped queries must match the tenant exactly — no OR IS NULL bleed."""
    base = select(_entities)
    filtered = apply_tenant_filter(base, _Model, tenant_id=42)
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True})).upper()

    assert "IS NULL" not in sql
    assert "TENANT_ID" in sql
    assert " OR " not in sql


def test_apply_tenant_filter_matches_nothing_when_tenant_missing():
    base = select(_entities)
    filtered = apply_tenant_filter(base, _Model, tenant_id=None)
    where = filtered.whereclause
    assert where is not None
    assert where.compare(false()) or "false" in str(where).lower()


def test_require_tenant_id_returns_explicit_tenant():
    assert require_tenant_id(7) == 7


def test_require_tenant_id_fails_closed_with_403():
    with pytest.raises(HTTPException) as exc:
        require_tenant_id(None)

    assert exc.value.status_code == 403
    detail = exc.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "TENANT_ACCESS_DENIED"


def test_audit_get_entity_source_is_fail_closed():
    """Guard against regressions that reintroduce NULL-inclusive OR in _get_entity."""
    import inspect

    from src.domain.services.audit_service import AuditService

    source = inspect.getsource(AuditService._get_entity)
    assert "is_(None)" not in source
    assert "tenant_id == tenant_id" in source or "model_any.tenant_id == tenant_id" in source
