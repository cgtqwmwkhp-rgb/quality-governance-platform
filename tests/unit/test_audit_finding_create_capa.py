"""Unit tests for POST finding → CAPA create (create_capa_for_finding)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.capa import CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.services.audit_service import AuditService


def _service() -> AuditService:
    return AuditService(MagicMock())


def _finding(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = dict(
        id=42,
        run_id=7,
        title="Missing PPE",
        description="Operator without gloves",
        severity="high",
        reference_number="AF-42",
        corrective_action_required=False,
        corrective_action_due_date=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _run(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = dict(
        id=7,
        tenant_id=1,
        assigned_to_id=99,
        assurance_scheme="ISO 45001",
        external_reference="8.1.2",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _mock_db(**methods: object) -> MagicMock:
    db = MagicMock()
    for name, value in methods.items():
        setattr(db, name, value)
    return db


@pytest.mark.asyncio
async def test_create_capa_for_finding_creates_linked_capa(monkeypatch: pytest.MonkeyPatch):
    service = _service()
    finding = _finding()
    run = _run()
    created: list[object] = []

    async def _get_entity(model: type, entity_id: int, *, tenant_id: int | None = None) -> object:
        if model.__name__ == "AuditFinding":
            assert entity_id == 42
            assert tenant_id == 1
            return finding
        if model.__name__ == "AuditRun":
            assert entity_id == 7
            return run
        raise AssertionError(f"unexpected model {model}")

    class _EmptyResult:
        def scalar_one_or_none(self) -> None:
            return None

    setattr(service, "_get_entity", _get_entity)
    service.db = _mock_db(
        execute=AsyncMock(return_value=_EmptyResult()),
        add=MagicMock(side_effect=lambda obj: created.append(obj)),
        flush=AsyncMock(),
        refresh=AsyncMock(),
    )

    monkeypatch.setattr(
        "src.domain.services.audit_service.ReferenceNumberService.generate",
        AsyncMock(return_value="CAPA-2026-0001"),
    )
    monkeypatch.setattr(
        "src.domain.services.audit_service.invalidate_tenant_cache",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "src.domain.services.audit_service.track_metric",
        MagicMock(),
    )
    monkeypatch.setattr(
        "src.domain.services.audit_service.record_audit_event",
        AsyncMock(),
    )

    action = await service.create_capa_for_finding(
        42,
        tenant_id=1,
        actor_user_id=5,
        title="Fix PPE gap",
        description="Issue gloves and retrain",
        assignee_email=None,
    )

    assert len(created) == 1
    assert action is created[0]
    assert action.reference_number == "CAPA-2026-0001"
    assert action.title == "Fix PPE gap"
    assert action.description == "Issue gloves and retrain"
    assert action.source_type == CAPASource.AUDIT_FINDING
    assert action.source_id == 42
    assert action.capa_type == CAPAType.CORRECTIVE
    assert action.status == CAPAStatus.OPEN
    assert action.priority == CAPAPriority.HIGH
    assert action.assigned_to_id == 99
    assert action.created_by_id == 5
    assert action.tenant_id == 1
    assert finding.corrective_action_required is True


@pytest.mark.asyncio
async def test_create_capa_for_finding_idempotent_returns_existing():
    service = _service()
    finding = _finding()
    run = _run()
    existing = SimpleNamespace(id=88, reference_number="CAPA-EXISTING", source_id=42)

    async def _get_entity(model: type, entity_id: int, *, tenant_id: int | None = None) -> object:
        if model.__name__ == "AuditFinding":
            return finding
        if model.__name__ == "AuditRun":
            return run
        raise AssertionError(f"unexpected model {model}")

    class _ExistingResult:
        def scalar_one_or_none(self) -> object:
            return existing

    setattr(service, "_get_entity", _get_entity)
    add_mock = MagicMock()
    service.db = _mock_db(
        execute=AsyncMock(return_value=_ExistingResult()),
        add=add_mock,
    )

    action = await service.create_capa_for_finding(
        42,
        tenant_id=1,
        actor_user_id=5,
    )

    assert action is existing
    add_mock.assert_not_called()


@pytest.mark.asyncio
async def test_create_capa_for_finding_404_when_missing():
    service = _service()

    async def _missing(*_a: object, **_k: object) -> object:
        raise NotFoundError("AuditFinding 999 not found")

    setattr(service, "_get_entity", _missing)

    with pytest.raises(NotFoundError, match="AuditFinding 999"):
        await service.create_capa_for_finding(999, tenant_id=1, actor_user_id=5)


@pytest.mark.asyncio
async def test_create_capa_for_finding_resolves_assignee_email(monkeypatch: pytest.MonkeyPatch):
    service = _service()
    finding = _finding()
    run = _run(assigned_to_id=None)
    created: list[object] = []

    async def _get_entity(model: type, entity_id: int, *, tenant_id: int | None = None) -> object:
        if model.__name__ == "AuditFinding":
            return finding
        if model.__name__ == "AuditRun":
            return run
        raise AssertionError(f"unexpected model {model}")

    class _EmptyResult:
        def scalar_one_or_none(self) -> None:
            return None

    class _UserResult:
        def scalar_one_or_none(self) -> object:
            return SimpleNamespace(id=55)

    execute_calls = {"n": 0}

    async def _execute(_stmt: object) -> object:
        execute_calls["n"] += 1
        if execute_calls["n"] == 1:
            return _EmptyResult()
        return _UserResult()

    setattr(service, "_get_entity", _get_entity)
    service.db = _mock_db(
        execute=AsyncMock(side_effect=_execute),
        add=MagicMock(side_effect=lambda obj: created.append(obj)),
        flush=AsyncMock(),
        refresh=AsyncMock(),
    )

    monkeypatch.setattr(
        "src.domain.services.audit_service.ReferenceNumberService.generate",
        AsyncMock(return_value="CAPA-2026-0002"),
    )
    monkeypatch.setattr(
        "src.domain.services.audit_service.invalidate_tenant_cache",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "src.domain.services.audit_service.track_metric",
        MagicMock(),
    )
    monkeypatch.setattr(
        "src.domain.services.audit_service.record_audit_event",
        AsyncMock(),
    )

    action = await service.create_capa_for_finding(
        42,
        tenant_id=1,
        actor_user_id=5,
        assignee_email="owner@example.com",
    )

    assert action.assigned_to_id == 55


@pytest.mark.asyncio
async def test_create_capa_for_finding_unknown_assignee_raises(monkeypatch: pytest.MonkeyPatch):
    service = _service()
    finding = _finding()
    run = _run()

    async def _get_entity(model: type, entity_id: int, *, tenant_id: int | None = None) -> object:
        if model.__name__ == "AuditFinding":
            return finding
        if model.__name__ == "AuditRun":
            return run
        raise AssertionError(f"unexpected model {model}")

    class _EmptyResult:
        def scalar_one_or_none(self) -> None:
            return None

    setattr(service, "_get_entity", _get_entity)
    service.db = _mock_db(execute=AsyncMock(return_value=_EmptyResult()))

    with pytest.raises(ValidationError, match="No user found"):
        await service.create_capa_for_finding(
            42,
            tenant_id=1,
            actor_user_id=5,
            assignee_email="missing@example.com",
        )


@pytest.mark.asyncio
async def test_create_capa_defaults_title_from_finding(monkeypatch: pytest.MonkeyPatch):
    service = _service()
    finding = _finding(title="Scaffold incomplete")
    run = _run()
    created: list[object] = []

    async def _get_entity(model: type, entity_id: int, *, tenant_id: int | None = None) -> object:
        if model.__name__ == "AuditFinding":
            return finding
        if model.__name__ == "AuditRun":
            return run
        raise AssertionError(f"unexpected model {model}")

    class _EmptyResult:
        def scalar_one_or_none(self) -> None:
            return None

    setattr(service, "_get_entity", _get_entity)
    service.db = _mock_db(
        execute=AsyncMock(return_value=_EmptyResult()),
        add=MagicMock(side_effect=lambda obj: created.append(obj)),
        flush=AsyncMock(),
        refresh=AsyncMock(),
    )

    monkeypatch.setattr(
        "src.domain.services.audit_service.ReferenceNumberService.generate",
        AsyncMock(return_value="CAPA-2026-0003"),
    )
    monkeypatch.setattr(
        "src.domain.services.audit_service.invalidate_tenant_cache",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "src.domain.services.audit_service.track_metric",
        MagicMock(),
    )
    monkeypatch.setattr(
        "src.domain.services.audit_service.record_audit_event",
        AsyncMock(),
    )

    action = await service.create_capa_for_finding(42, tenant_id=1, actor_user_id=5)

    assert action.title == "Action plan: Scaffold incomplete"
    assert action.description == finding.description


@pytest.mark.asyncio
async def test_create_capa_tenant_isolation_on_lookup():
    """Missing finding for tenant surfaces NotFoundError (fail-closed)."""
    service = _service()

    with patch.object(
        AuditService,
        "_get_entity",
        AsyncMock(side_effect=NotFoundError("AuditFinding 42 not found")),
    ):
        with pytest.raises(NotFoundError):
            await service.create_capa_for_finding(42, tenant_id=2, actor_user_id=5)
