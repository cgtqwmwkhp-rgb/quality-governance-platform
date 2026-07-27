"""Regression suite: an investigation's open-work probe belongs to the record.

B-5, found while reviewing #1382. That PR established for incidents, complaints,
near misses and RTAs that the closure gate's open-work probe must be scoped to
**the record's** tenant: probing the caller's tenant for a record that lives in
another one finds none of that record's actions, and a gate that then reports a
clean close is the worst thing an evidence system can do.

``investigation_closure_helpers`` had the opposite bias. Both the validation path
and ``_ensure_investigation_ready_for_status`` derived the scope from
``current_user.tenant_id``, and ``_get_investigation_or_404`` applies no tenant
filter at all — superusers, ``investigations:view_all`` holders and anyone named
on the run can load one belonging to another tenant. The open-work probe
therefore searched the wrong tenant and reported ``open_work: []``.

The probe scope is now a property of the run, and where the run's tenant and the
caller's differ we refuse rather than probe either one.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.investigations import _collect_readiness_reasons, get_closure_validation, update_investigation
from src.api.schemas.investigation import InvestigationRunUpdate
from src.domain.exceptions import StateTransitionError, TenantAccessError
from src.domain.models.investigation import AssignedEntityType, InvestigationStatus
from src.domain.services.case_closure import CLOSURE_REASON_TENANT_SCOPE_UNRESOLVED
from src.domain.services.investigation_closure_helpers import (
    CLOSURE_REASON_OPEN_ACTIONS_REMAIN,
    OpenWorkItem,
    resolve_investigation_closure_scope,
)
from src.domain.services.investigation_service import InvestigationService


def _run(**overrides):
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=7,
        tenant_id=7,
        template_id=1,
        level="medium",
        status=InvestigationStatus.COMPLETED,
        started_at="2026-07-01T00:00:00",
        completed_at="2026-07-02T00:00:00",
        closed_at=None,
        assigned_to_user_id=42,
        reviewer_user_id=None,
        approved_by_id=None,
        created_by_id=42,
        assigned_entity_type=AssignedEntityType.REPORTING_INCIDENT,
        assigned_entity_id=20,
        title="Warehouse slip investigation",
        reference_number="REF-2026-0007",
        created_at=now,
        updated_at=now,
        updated_by_id=1,
        data={
            "findings": "Slip on wet floor",
            "conclusion": "Improve housekeeping",
            "lead_investigator": "pat@example.com",
        },
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _user(*, tenant_id: int | None = 1, is_superuser: bool = True):
    return SimpleNamespace(id=42, tenant_id=tenant_id, is_superuser=is_superuser)


def _db_returning(row):
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    result.scalar_one.return_value = row
    result.scalars.return_value.all.return_value = []
    result.scalars.return_value.first.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _open_action():
    return OpenWorkItem(
        kind="investigation_action",
        id=3,
        reference_number="INV-ACT-3",
        title="Re-lay the warehouse floor",
        status="open",
        action_key="investigation_action:3",
    )


def _empty_template_validation():
    result = MagicMock()
    result.reason_codes = []
    result.missing_items = []
    return result


def _probe(items):
    return patch(
        "src.domain.services.investigation_closure_helpers.fetch_open_work_for_investigation",
        AsyncMock(return_value=items),
    )


def _quiet_template_validation():
    return patch.object(
        InvestigationService,
        "validate_closure",
        AsyncMock(return_value=_empty_template_validation()),
    )


class TestProbeScopeIsTheRecords:
    def test_scope_is_the_runs_own_tenant(self):
        assert resolve_investigation_closure_scope(_run(tenant_id=9), caller_tenant_id=9) == 9

    def test_no_caller_may_hand_the_gate_a_probe_scope(self):
        """Validation and enforcement cannot disagree on scope if neither supplies one."""
        params = list(inspect.signature(_collect_readiness_reasons).parameters)

        assert "tenant_id" not in params
        assert "current_user" in params

    @pytest.mark.asyncio
    async def test_same_tenant_probes_the_records_tenant_and_reports_its_work(self):
        run = _run(tenant_id=7)

        with _probe([_open_action()]) as probe, _quiet_template_validation():
            reasons, open_work, _missing = await _collect_readiness_reasons(
                _db_returning(run),
                investigation=run,
                investigation_id=7,
                current_user=_user(tenant_id=7),
                gate="close",
            )

        assert probe.await_args.kwargs["tenant_id"] == 7
        assert reasons == [CLOSURE_REASON_OPEN_ACTIONS_REMAIN]
        assert [item.action_key for item in open_work] == ["investigation_action:3"]

    @pytest.mark.asyncio
    async def test_cross_tenant_caller_is_refused_instead_of_probing_the_wrong_tenant(self):
        """The defect: tenant 1 asked about tenant 7's run and was told nothing was open."""
        run = _run(tenant_id=7)

        with _probe([_open_action()]) as probe, _quiet_template_validation():
            with pytest.raises(TenantAccessError):
                await _collect_readiness_reasons(
                    _db_returning(run),
                    investigation=run,
                    investigation_id=7,
                    current_user=_user(tenant_id=1),
                    gate="close",
                )

        assert probe.await_count == 0

    @pytest.mark.asyncio
    async def test_a_tenantless_caller_cannot_borrow_the_records_scope(self):
        run = _run(tenant_id=7)

        with _probe([]) as probe, _quiet_template_validation():
            with pytest.raises(TenantAccessError):
                await _collect_readiness_reasons(
                    _db_returning(run),
                    investigation=run,
                    investigation_id=7,
                    current_user=_user(tenant_id=None),
                    gate="close",
                )

        assert probe.await_count == 0

    def test_a_tenantless_run_is_refused_under_its_own_code(self):
        """A corrupt row is not "no open actions", and it is not a caller problem."""
        with pytest.raises(StateTransitionError) as exc_info:
            resolve_investigation_closure_scope(_run(tenant_id=None), caller_tenant_id=1)

        assert exc_info.value.code == CLOSURE_REASON_TENANT_SCOPE_UNRESOLVED
        assert exc_info.value.code != CLOSURE_REASON_OPEN_ACTIONS_REMAIN


class TestValidationAndCloseAgreeOnScope:
    """Whatever the readiness read refuses, the close must refuse the same way."""

    @pytest.mark.asyncio
    async def test_both_paths_refuse_a_cross_tenant_run_identically(self):
        async def validation_outcome():
            try:
                await get_closure_validation(7, _db_returning(_run(tenant_id=7)), _user(tenant_id=1))
            except TenantAccessError as exc:
                return ("refused", exc.code)
            return ("ok", ())

        async def close_outcome():
            try:
                await update_investigation(
                    request=MagicMock(headers={"X-Request-ID": "req-cross-tenant"}),
                    investigation_id=7,
                    investigation_data=InvestigationRunUpdate(status="closed"),
                    db=_db_returning(_run(tenant_id=7)),
                    current_user=_user(tenant_id=1),
                )
            except TenantAccessError as exc:
                return ("refused", exc.code)
            return ("closed", ())

        with _probe([_open_action()]), _quiet_template_validation():
            validation = await validation_outcome()
            close = await close_outcome()

        assert validation == close
        assert validation == ("refused", "TENANT_ACCESS_DENIED")

    @pytest.mark.asyncio
    async def test_a_cross_tenant_close_never_reports_a_clean_gate(self):
        """Before the fix this closed the run: the probe found none of its work."""
        run = _run(tenant_id=7)

        with _probe([_open_action()]), _quiet_template_validation():
            with pytest.raises(TenantAccessError):
                await update_investigation(
                    request=MagicMock(headers={"X-Request-ID": "req-cross-tenant-close"}),
                    investigation_id=7,
                    investigation_data=InvestigationRunUpdate(status="closed"),
                    db=_db_returning(run),
                    current_user=_user(tenant_id=1),
                )

        assert run.closed_at is None
        assert run.status == InvestigationStatus.COMPLETED
