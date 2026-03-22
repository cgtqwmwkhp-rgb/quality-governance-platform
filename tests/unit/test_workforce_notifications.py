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
        tenant_id=3,
    )

    assert db.add.call_count == 1
    assert db.add.call_args[0][0].user_id == 7
    assert db.add.call_args[0][0].tenant_id == 3


@pytest.mark.asyncio
async def test_induction_notification_skips_missing_engineer_user():
    db = types.SimpleNamespace(add=Mock())

    await NotificationService.notify_induction_complete(
        db=db,
        induction_run_id="ind-1",
        engineer_user_id=None,
        supervisor_id=7,
        not_yet_competent_count=0,
        tenant_id=3,
    )

    assert db.add.call_count == 1
    assert db.add.call_args[0][0].user_id == 7
    assert db.add.call_args[0][0].tenant_id == 3


@pytest.mark.asyncio
async def test_induction_notification_notifies_engineer_and_supervisor():
    db = types.SimpleNamespace(add=Mock())

    await NotificationService.notify_induction_complete(
        db=db,
        induction_run_id="ind-2",
        engineer_user_id=11,
        supervisor_id=7,
        not_yet_competent_count=2,
        tenant_id=5,
    )

    assert db.add.call_count == 2
    engineer_notification = db.add.call_args_list[0][0][0]
    supervisor_notification = db.add.call_args_list[1][0][0]
    assert engineer_notification.user_id == 11
    assert supervisor_notification.user_id == 7
    assert engineer_notification.tenant_id == 5
    assert supervisor_notification.tenant_id == 5
