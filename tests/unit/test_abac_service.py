"""Tests for src.domain.services.abac_service."""

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_perm_mod_key = "src.domain.models.permissions"
if _perm_mod_key not in sys.modules:
    _fake_perm = ModuleType(_perm_mod_key)
    for _cls_name in (
        "ABACPolicy",
        "FieldLevelPermission",
        "Permission",
        "PermissionAudit",
        "Role",
        "RolePermission",
    ):
        setattr(_fake_perm, _cls_name, type(_cls_name, (), {}))
    _FakeUserRole = type(
        "UserRole",
        (),
        {
            "user_id": MagicMock(),
            "tenant_id": MagicMock(),
            "role_id": MagicMock(),
            "is_active": MagicMock(),
        },
    )
    setattr(_fake_perm, "UserRole", _FakeUserRole)
    sys.modules[_perm_mod_key] = _fake_perm

from src.domain.services.abac_service import ABACService  # noqa: E402


def _mock_scalar(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_scalars(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


# ---------------------------------------------------------------------------
# _compare operator tests
# ---------------------------------------------------------------------------


class TestCompare:
    @pytest.fixture
    def service(self):
        return ABACService(AsyncMock())

    def test_eq(self, service):
        assert service._compare(5, "eq", 5) is True
        assert service._compare(5, "eq", 6) is False

    def test_ne(self, service):
        assert service._compare(5, "ne", 6) is True
        assert service._compare(5, "ne", 5) is False

    def test_gt(self, service):
        assert service._compare(10, "gt", 5) is True
        assert service._compare(5, "gt", 10) is False
        assert service._compare(None, "gt", 5) is False

    def test_gte(self, service):
        assert service._compare(5, "gte", 5) is True
        assert service._compare(4, "gte", 5) is False

    def test_lt(self, service):
        assert service._compare(3, "lt", 5) is True
        assert service._compare(5, "lt", 3) is False
        assert service._compare(None, "lt", 5) is False

    def test_lte(self, service):
        assert service._compare(5, "lte", 5) is True
        assert service._compare(6, "lte", 5) is False

    def test_in(self, service):
        assert service._compare("admin", "in", ["admin", "manager"]) is True
        assert service._compare("user", "in", ["admin", "manager"]) is False
        assert service._compare("x", "in", []) is False

    def test_nin(self, service):
        assert service._compare("user", "nin", ["admin"]) is True
        assert service._compare("admin", "nin", ["admin"]) is False
        assert service._compare("x", "nin", []) is True

    def test_contains(self, service):
        assert service._compare("hello world", "contains", "world") is True
        assert service._compare("hello", "contains", "xyz") is False
        assert service._compare(None, "contains", "x") is False

    def test_regex(self, service):
        assert service._compare("admin@test.com", "regex", r".*@test\.com") is True
        assert service._compare("admin@other.com", "regex", r".*@test\.com") is False
        assert service._compare(None, "regex", r".*") is False

    def test_exists(self, service):
        assert service._compare("value", "exists", True) is True
        assert service._compare(None, "exists", True) is False
        assert service._compare(None, "exists", False) is True

    def test_unknown_operator(self, service):
        assert service._compare(5, "unknown_op", 5) is False


# ---------------------------------------------------------------------------
# _evaluate_conditions
# ---------------------------------------------------------------------------


class TestEvaluateConditions:
    @pytest.fixture
    def service(self):
        return ABACService(AsyncMock())

    def test_direct_equality_match(self, service):
        assert service._evaluate_conditions({"role": "admin"}, {"role": "admin"}) is True

    def test_direct_equality_no_match(self, service):
        assert service._evaluate_conditions({"role": "admin"}, {"role": "user"}) is False

    def test_list_membership(self, service):
        assert service._evaluate_conditions({"role": ["admin", "manager"]}, {"role": "admin"}) is True

    def test_list_no_membership(self, service):
        assert service._evaluate_conditions({"role": ["admin", "manager"]}, {"role": "viewer"}) is False

    def test_operator_comparison(self, service):
        assert service._evaluate_conditions({"clearance": {"gte": 3}}, {"clearance": 5}) is True

    def test_variable_substitution(self, service):
        assert (
            service._evaluate_conditions(
                {"owner_id": {"eq": "$subject.id"}},
                {"owner_id": 42},
                subject_context={"id": 42},
            )
            is True
        )

    def test_variable_substitution_no_match(self, service):
        assert (
            service._evaluate_conditions(
                {"owner_id": {"eq": "$subject.id"}},
                {"owner_id": 42},
                subject_context={"id": 99},
            )
            is False
        )

    def test_multiple_conditions_all_must_match(self, service):
        assert (
            service._evaluate_conditions(
                {"role": "admin", "department": "IT"},
                {"role": "admin", "department": "IT"},
            )
            is True
        )
        assert (
            service._evaluate_conditions(
                {"role": "admin", "department": "IT"},
                {"role": "admin", "department": "HR"},
            )
            is False
        )


# ---------------------------------------------------------------------------
# _evaluate_policy
# ---------------------------------------------------------------------------


class TestEvaluatePolicy:
    @pytest.fixture
    def service(self):
        return ABACService(AsyncMock())

    def test_no_conditions_matches(self, service):
        policy = MagicMock(
            subject_conditions={},
            resource_conditions={},
            environment_conditions={},
        )
        assert service._evaluate_policy(policy, {}, {}, {}) is True

    def test_subject_condition_blocks(self, service):
        policy = MagicMock(
            subject_conditions={"role": "admin"},
            resource_conditions={},
            environment_conditions={},
        )
        assert service._evaluate_policy(policy, {"role": "user"}, {}, {}) is False

    def test_resource_condition_blocks(self, service):
        policy = MagicMock(
            subject_conditions={},
            resource_conditions={"status": "draft"},
            environment_conditions={},
        )
        assert service._evaluate_policy(policy, {}, {"status": "published"}, {}) is False

    def test_environment_condition_blocks(self, service):
        policy = MagicMock(
            subject_conditions={},
            resource_conditions={},
            environment_conditions={"time_of_day": "business_hours"},
        )
        assert service._evaluate_policy(policy, {}, {}, {"time_of_day": "night"}) is False


# ---------------------------------------------------------------------------
# _apply_mask_pattern
# ---------------------------------------------------------------------------


class TestApplyMaskPattern:
    @pytest.fixture
    def service(self):
        return ABACService(AsyncMock())

    def test_last4_pattern(self, service):
        result = service._apply_mask_pattern("4111111111111234", "****{last4}")
        assert result == "****1234"

    def test_short_value(self, service):
        result = service._apply_mask_pattern("12", "****{last4}")
        assert result == "****12"

    def test_no_pattern_returns_pattern(self, service):
        result = service._apply_mask_pattern("value", "MASKED")
        assert result == "MASKED"


# ---------------------------------------------------------------------------
# _invalidate_policy_cache
# ---------------------------------------------------------------------------


class TestInvalidatePolicyCache:
    @pytest.fixture
    def service(self):
        svc = ABACService(AsyncMock())
        svc._policy_cache = {
            "1:incident:create": [],
            "1:incident:read": [],
            "1:risk:create": [],
        }
        return svc

    def test_invalidate_specific(self, service):
        service._invalidate_policy_cache("incident", "create")
        assert "1:incident:create" not in service._policy_cache
        assert "1:incident:read" in service._policy_cache

    def test_invalidate_all(self, service):
        service._invalidate_policy_cache()
        assert service._policy_cache == {}


# ---------------------------------------------------------------------------
# check_permission
# ---------------------------------------------------------------------------


class TestCheckPermission:
    @pytest.fixture
    def service(self):
        svc = ABACService(AsyncMock())
        svc._log_permission_check = MagicMock()
        return svc

    @pytest.mark.asyncio
    async def test_default_deny_no_policies(self, service):
        service._get_applicable_policies = AsyncMock(return_value=[])

        allowed, policy = await service.check_permission(
            subject={"id": 1},
            resource_type="incident",
            action="create",
        )
        assert allowed is False
        assert policy is None

    @pytest.mark.asyncio
    async def test_allow_when_policy_matches(self, service):
        policy_mock = MagicMock(
            effect="allow",
            priority=10,
            id=1,
            subject_conditions={},
            resource_conditions={},
            environment_conditions={},
        )
        service._get_applicable_policies = AsyncMock(return_value=[policy_mock])

        allowed, matched = await service.check_permission(
            subject={"id": 1},
            resource_type="incident",
            action="create",
        )
        assert allowed is True
        assert matched is policy_mock

    @pytest.mark.asyncio
    async def test_deny_overrides_allow(self, service):
        deny_policy = MagicMock(
            effect="deny",
            priority=10,
            id=1,
            subject_conditions={},
            resource_conditions={},
            environment_conditions={},
        )
        allow_policy = MagicMock(
            effect="allow",
            priority=10,
            id=2,
            subject_conditions={},
            resource_conditions={},
            environment_conditions={},
        )
        service._get_applicable_policies = AsyncMock(return_value=[deny_policy, allow_policy])

        allowed, matched = await service.check_permission(
            subject={"id": 1},
            resource_type="incident",
            action="create",
        )
        assert allowed is False

    @pytest.mark.asyncio
    async def test_higher_priority_wins(self, service):
        low = MagicMock(
            effect="deny",
            priority=1,
            id=1,
            subject_conditions={},
            resource_conditions={},
            environment_conditions={},
        )
        high = MagicMock(
            effect="allow",
            priority=100,
            id=2,
            subject_conditions={},
            resource_conditions={},
            environment_conditions={},
        )
        service._get_applicable_policies = AsyncMock(return_value=[low, high])

        allowed, matched = await service.check_permission(
            subject={"id": 1},
            resource_type="incident",
            action="create",
        )
        assert allowed is True


# ---------------------------------------------------------------------------
# check_permission_simple
# ---------------------------------------------------------------------------


class TestCheckPermissionSimple:
    @pytest.fixture
    def service(self):
        return ABACService(AsyncMock())

    @pytest.fixture(autouse=True)
    def _mock_select(self):
        with patch("src.domain.services.abac_service.select", return_value=MagicMock()):
            yield

    @pytest.mark.asyncio
    async def test_no_roles_returns_false(self, service):
        service.db.execute.return_value = _mock_scalars([])

        result = await service.check_permission_simple(1, "incident", "create", 1)
        assert result is False

    @pytest.mark.asyncio
    async def test_matching_permission(self, service):
        user_role = MagicMock(role_id=1)
        service.db.execute.return_value = _mock_scalars([user_role])
        service._get_role_permissions = AsyncMock(return_value={"incident.create", "incident.read"})

        result = await service.check_permission_simple(1, "incident", "create", 1)
        assert result is True

    @pytest.mark.asyncio
    async def test_wildcard_permission(self, service):
        user_role = MagicMock(role_id=1)
        service.db.execute.return_value = _mock_scalars([user_role])
        service._get_role_permissions = AsyncMock(return_value={"incident.*"})

        result = await service.check_permission_simple(1, "incident", "delete", 1)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_matching_permission(self, service):
        user_role = MagicMock(role_id=1)
        service.db.execute.return_value = _mock_scalars([user_role])
        service._get_role_permissions = AsyncMock(return_value={"risk.read"})

        result = await service.check_permission_simple(1, "incident", "create", 1)
        assert result is False
