"""Unit tests for investigation comment tenant_id write-path safety."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.routes import investigations as investigation_routes
from src.domain.exceptions import ValidationError
from src.domain.models.investigation import InvestigationComment, InvestigationRun
from src.domain.services.investigation_service import InvestigationService


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def _investigation(*, tenant_id: int | None) -> InvestigationRun:
    return InvestigationRun(
        id=101,
        tenant_id=tenant_id,
        created_by_id=7,
        updated_by_id=7,
        version=3,
    )


def _db_returning(investigation: InvestigationRun):
    return SimpleNamespace(
        execute=AsyncMock(return_value=_ScalarResult(investigation)),
        add=MagicMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )


def _user(*, tenant_id: int):
    return SimpleNamespace(
        id=7,
        tenant_id=tenant_id,
        is_superuser=False,
        has_permission=lambda _permission: False,
    )


@pytest.mark.asyncio
async def test_route_create_comment_inherits_tenant_id_from_investigation():
    db = _db_returning(_investigation(tenant_id=24))
    payload = investigation_routes.AddCommentRequest(content="Needs follow-up")

    await investigation_routes.add_comment(
        investigation_id=101,
        payload=payload,
        db=db,
        current_user=_user(tenant_id=24),
    )

    comment = db.add.call_args_list[0].args[0]
    assert isinstance(comment, InvestigationComment)
    assert comment.tenant_id == 24
    assert comment.investigation_id == 101


@pytest.mark.asyncio
async def test_route_create_comment_fails_closed_when_investigation_has_no_tenant_id():
    db = _db_returning(_investigation(tenant_id=None))
    payload = investigation_routes.AddCommentRequest(content="Needs follow-up")

    with pytest.raises(ValidationError, match="tenant_id is required to create an investigation comment"):
        await investigation_routes.add_comment(
            investigation_id=101,
            payload=payload,
            db=db,
            current_user=_user(tenant_id=24),
        )

    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_add_comment_inherits_tenant_id_from_investigation():
    db = _db_returning(_investigation(tenant_id=24))

    comment = await InvestigationService.add_comment(
        db,
        investigation_id=101,
        body="Needs follow-up",
        section_id=None,
        field_id=None,
        parent_comment_id=None,
        tenant_id=24,
        user_id=7,
    )

    assert isinstance(comment, InvestigationComment)
    assert comment.tenant_id == 24
    assert db.add.call_args_list[0].args[0] is comment


@pytest.mark.asyncio
async def test_service_add_comment_fails_closed_when_investigation_has_no_tenant_id():
    db = _db_returning(_investigation(tenant_id=None))

    with pytest.raises(ValidationError, match="tenant_id is required to create an investigation comment"):
        await InvestigationService.add_comment(
            db,
            investigation_id=101,
            body="Needs follow-up",
            section_id=None,
            field_id=None,
            parent_comment_id=None,
            tenant_id=24,
            user_id=7,
        )

    db.add.assert_not_called()
    db.commit.assert_not_awaited()
