"""Unit tests: InvestigationService.add_comment stamps tenant_id from investigation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import ValidationError
from src.domain.models.investigation import InvestigationComment
from src.domain.services.investigation_service import InvestigationService


@pytest.mark.asyncio
async def test_add_comment_sets_tenant_id_from_investigation():
    investigation = MagicMock()
    investigation.id = 42
    investigation.tenant_id = 7
    investigation.version = 1

    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with (
        patch.object(
            InvestigationService,
            "get_investigation",
            new=AsyncMock(return_value=investigation),
        ),
        patch.object(
            InvestigationService,
            "create_revision_event",
            new=AsyncMock(),
        ),
    ):
        comment = await InvestigationService.add_comment(
            db,
            investigation_id=42,
            body="Note body",
            section_id=None,
            field_id=None,
            parent_comment_id=None,
            tenant_id=7,
            user_id=3,
        )

    assert isinstance(comment, InvestigationComment)
    assert comment.tenant_id == 7
    assert comment.investigation_id == 42
    assert comment.content == "Note body"
    assert comment.author_id == 3
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_comment_rejects_missing_investigation_tenant_id():
    investigation = MagicMock()
    investigation.id = 42
    investigation.tenant_id = None

    db = AsyncMock()

    with patch.object(
        InvestigationService,
        "get_investigation",
        new=AsyncMock(return_value=investigation),
    ):
        with pytest.raises(ValidationError, match="tenant_id is required"):
            await InvestigationService.add_comment(
                db,
                investigation_id=42,
                body="Note body",
                section_id=None,
                field_id=None,
                parent_comment_id=None,
                tenant_id=7,
                user_id=3,
            )
