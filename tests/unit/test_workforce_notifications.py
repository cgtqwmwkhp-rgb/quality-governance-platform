import types
from unittest.mock import Mock

import pytest

from src.domain.services.governance_service import NotificationService


@pytest.mark.asyncio
async def test_assessment_notification_skips_missing_engineer_user():
    db = types.SimpleNamespace(add=Mock())

    await NotificationService.notify_assessment_complete(
        db=db,
        assessment_run_id="asm-1",
        engineer_user_id=None,
        supervisor_id=7,
        outcome="pass",
    )

    assert db.add.call_count == 1
    assert db.add.call_args[0][0].user_id == 7


@pytest.mark.asyncio
async def test_induction_notification_skips_missing_engineer_user():
    db = types.SimpleNamespace(add=Mock())

    await NotificationService.notify_induction_complete(
        db=db,
        induction_run_id="ind-1",
        engineer_user_id=None,
        supervisor_id=7,
        not_yet_competent_count=0,
    )

    db.add.assert_not_called()
