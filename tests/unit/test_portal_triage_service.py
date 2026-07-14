"""Unit tests for portal intake triage assign + notify helpers."""

from types import SimpleNamespace

import pytest

from src.domain.services.portal_triage_service import (
    apply_portal_owner,
    pick_triage_owner_from_users,
)


def _role(name: str, permissions: str = "") -> SimpleNamespace:
    return SimpleNamespace(name=name, permissions=permissions)


def _user(
    user_id: int,
    *,
    is_superuser: bool = False,
    is_active: bool = True,
    roles: list | None = None,
) -> SimpleNamespace:
    user = SimpleNamespace(
        id=user_id,
        is_superuser=is_superuser,
        is_active=is_active,
        roles=roles or [],
        tenant_id=1,
    )

    def has_permission(permission: str) -> bool:
        if is_superuser:
            return True
        for role in user.roles:
            perms = role.permissions or ""
            if permission in [p.strip() for p in perms.split(",") if p.strip()]:
                return True
        return False

    user.has_permission = has_permission
    return user


def test_pick_triage_owner_prefers_authenticated_submitter_with_permission() -> None:
    submitter = _user(
        7,
        roles=[_role("manager", permissions="incident:update,incident:read")],
    )
    pool = [
        _user(1, roles=[_role("admin", permissions="incident:update")]),
        _user(2, is_superuser=True),
    ]
    assert pick_triage_owner_from_users(pool, "incident", submitter=submitter, tenant_id=1) == 7


def test_pick_triage_owner_falls_back_to_superuser_in_pool() -> None:
    pool = [
        _user(1, roles=[_role("viewer", permissions="incident:read")]),
        _user(2, is_superuser=True),
    ]
    assert pick_triage_owner_from_users(pool, "incident", tenant_id=1) == 2


def test_pick_triage_owner_uses_update_permission_when_no_superuser() -> None:
    pool = [
        _user(1, roles=[_role("viewer", permissions="incident:read")]),
        _user(3, roles=[_role("clerk", permissions="complaint:update")]),
        _user(4, roles=[_role("coordinator", permissions="incident:update")]),
    ]
    assert pick_triage_owner_from_users(pool, "incident", tenant_id=1) == 4


def test_pick_triage_owner_returns_none_when_no_active_users() -> None:
    pool = [_user(1, is_active=False)]
    assert pick_triage_owner_from_users(pool, "incident", tenant_id=1) is None


@pytest.mark.parametrize(
    ("entity_type", "field_name"),
    [
        ("incident", "owner_id"),
        ("complaint", "owner_id"),
        ("rta", "owner_id"),
        ("near_miss", "assigned_to_id"),
    ],
)
def test_apply_portal_owner_sets_correct_field(entity_type: str, field_name: str) -> None:
    entity = SimpleNamespace()
    apply_portal_owner(entity, entity_type, 42)
    assert getattr(entity, field_name) == 42
