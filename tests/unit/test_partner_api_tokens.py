"""Unit tests for R6 partner API tokens."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.domain.models.partner_api_token import PARTNER_API_SCOPES, PartnerApiToken
from src.domain.services.partner_auth_service import (
    PartnerAuthService,
    generate_partner_token,
    hash_partner_token,
    verify_partner_token,
)

MIGRATION = Path("alembic/versions/20260717_partner_api_tokens.py")


def test_partner_api_scopes_v1():
    assert PARTNER_API_SCOPES == ("webhooks:manage", "inspections:read")


def test_partner_api_token_orm_columns():
    assert PartnerApiToken.__tablename__ == "partner_api_tokens"
    assert PartnerApiToken.__table__.c.secret_hash.nullable is False
    assert PartnerApiToken.__table__.c.token_prefix.nullable is False
    index_names = {index.name for index in PartnerApiToken.__table__.indexes}
    assert "ix_partner_api_tokens_tenant_active" in index_names
    assert "ix_partner_api_tokens_prefix" in index_names


def test_partner_api_tokens_migration_scaffold():
    assert MIGRATION.is_file()
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260717_partner_api_tokens"' in text
    assert 'down_revision: Union[str, Sequence[str], None] = "20260717_ocr_artifacts"' in text
    assert "partner_api_tokens" in text


def test_generate_partner_token_format_and_hash():
    raw, secret_hash, prefix = generate_partner_token()
    assert raw.startswith("qgp_pt_")
    assert prefix == raw[:16]
    assert secret_hash == hash_partner_token(raw)
    assert verify_partner_token(raw, secret_hash) is True
    assert verify_partner_token("qgp_pt_wrong", secret_hash) is False


@pytest.mark.asyncio
async def test_create_token_persists_hashed_secret():
    db = AsyncMock()
    service = PartnerAuthService(db)
    token, raw = await service.create_token(
        tenant_id=10,
        name="Integration A",
        scopes=["webhooks:manage"],
    )
    assert token.tenant_id == 10
    assert token.name == "Integration A"
    assert token.scopes == ["webhooks:manage"]
    assert token.is_active is True
    assert token.secret_hash == hash_partner_token(raw)
    assert raw.startswith("qgp_pt_")
    db.add.assert_called_once()
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_create_token_rejects_invalid_scope():
    db = AsyncMock()
    service = PartnerAuthService(db)
    with pytest.raises(ValueError, match="Unsupported scope"):
        await service.create_token(tenant_id=10, scopes=["admin:all"])


@pytest.mark.asyncio
async def test_revoke_token_sets_inactive_and_timestamp():
    db = AsyncMock()
    service = PartnerAuthService(db)
    token = PartnerApiToken(
        id=1,
        tenant_id=10,
        token_prefix="qgp_pt_abc",
        secret_hash="abc123",
        scopes=["webhooks:manage"],
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    revoked = await service.revoke_token(token)
    assert revoked.is_active is False
    assert revoked.revoked_at is not None
    db.flush.assert_awaited()


class _ScalarsResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


@pytest.mark.asyncio
async def test_list_tokens_excludes_revoked_by_default():
    active = PartnerApiToken(
        id=1,
        tenant_id=10,
        token_prefix="qgp_pt_active",
        secret_hash="hash1",
        scopes=["webhooks:manage"],
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarsResult([active]))
    service = PartnerAuthService(db)
    tokens = await service.list_tokens(10)
    assert tokens == [active]
