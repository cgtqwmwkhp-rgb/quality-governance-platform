"""C-18: verifying a sub-range of the audit hash chain must not invent tampering.

``verify_chain`` narrows its query with ``sequence >= start_sequence`` but then
seeds the running ``previous_hash`` with ``GENESIS_HASH`` regardless. The first
entry in any range that does not start at sequence 1 is therefore compared
against ``"0" * 64`` rather than against its real predecessor, so it is reported
as "Previous hash mismatch" on a chain nobody has touched.

That matters more than the size of the bug suggests. Verifying a narrow window
is exactly what an auditor does when a specific record is contested — checking
the whole tenant's history to answer a question about one deletion is not what
anyone reaches for. So the single most likely verification is the one that
raises a false alarm, which is worse than useless: it teaches the reader that
the mismatch report cannot be trusted.

These tests seed a real chain through ``AuditLogService.log`` (no hand-built
hashes, so the chain is exactly what production writes) and then verify
sub-ranges of it.
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.models.audit_log import AuditLogEntry
from src.domain.services.audit_log_service import AuditLogService

pytestmark = pytest.mark.asyncio

CHAIN_LENGTH = 5


async def _seed_chain(session, tenant_id: int, count: int = CHAIN_LENGTH) -> list[AuditLogEntry]:
    """Write *count* genuine, untampered chain entries for *tenant_id*."""
    service = AuditLogService(session)
    entries = []
    for i in range(count):
        entry = await service.log(
            tenant_id=tenant_id,
            entity_type="incident",
            entity_id=str(100 + i),
            action="update",
            user_id=1,
            new_values={"step": i},
            commit=True,
        )
        entries.append(entry)
    return entries


@pytest.fixture
async def chain_tenant(test_session):
    """A tenant of its own, so this chain starts at sequence 1 and nothing else writes to it."""
    from tests.factories import TenantFactory

    tenant = TenantFactory.build(
        name="Chain Verification Tenant",
        slug=f"chain-verify-{uuid.uuid4().hex[:8]}",
        admin_email="chain@test.example.com",
        is_active=True,
    )
    test_session.add(tenant)
    await test_session.commit()
    await test_session.refresh(tenant)
    return tenant


async def test_seeded_chain_is_genuinely_intact(test_session, chain_tenant):
    """Baseline: a full-range verification of the seeded chain passes.

    Without this, a partial-range failure below could just mean "the fixture
    wrote a broken chain", and the whole module would prove nothing.
    """
    entries = await _seed_chain(test_session, chain_tenant.id)
    assert [e.sequence for e in entries] == [1, 2, 3, 4, 5]

    verification = await AuditLogService(test_session).verify_chain(tenant_id=chain_tenant.id)

    assert verification.is_valid is True, f"seeded chain is not intact: {verification.invalid_entries}"
    assert verification.entries_verified == CHAIN_LENGTH


async def test_partial_verification_from_mid_chain_reports_no_tampering(test_session, chain_tenant):
    """C-18: verifying from sequence 3 of an untouched chain must report valid."""
    await _seed_chain(test_session, chain_tenant.id)

    verification = await AuditLogService(test_session).verify_chain(
        tenant_id=chain_tenant.id,
        start_sequence=3,
    )

    assert verification.entries_verified == 3, "expected sequences 3, 4 and 5 to be in range"
    assert verification.is_valid is True, (
        "partial verification of an untampered chain reported tampering: " f"{verification.invalid_entries}"
    )
    assert verification.invalid_entries is None


async def test_partial_verification_does_not_blame_the_first_entry_in_range(test_session, chain_tenant):
    """The specific false positive: entry 3 compared against the genesis hash.

    Asserted separately from ``is_valid`` so that a regression names the entry
    it wrongly accuses rather than only reporting that something went wrong.
    """
    await _seed_chain(test_session, chain_tenant.id)

    verification = await AuditLogService(test_session).verify_chain(
        tenant_id=chain_tenant.id,
        start_sequence=3,
    )

    accused = {e["sequence"] for e in (verification.invalid_entries or [])}
    assert 3 not in accused, (
        "sequence 3 was reported as a previous-hash mismatch because the range "
        "was seeded with GENESIS_HASH instead of entry 2's hash: "
        f"{verification.invalid_entries}"
    )


async def test_bounded_window_in_the_middle_of_the_chain_is_valid(test_session, chain_tenant):
    """A window with both bounds set (the 'check around one change' case) is valid."""
    await _seed_chain(test_session, chain_tenant.id)

    verification = await AuditLogService(test_session).verify_chain(
        tenant_id=chain_tenant.id,
        start_sequence=2,
        end_sequence=4,
    )

    assert verification.entries_verified == 3
    assert verification.is_valid is True, f"bounded mid-chain window reported tampering: {verification.invalid_entries}"


async def test_full_range_started_explicitly_at_one_still_uses_genesis(test_session, chain_tenant):
    """start_sequence=1 is the genuine genesis case and must still be checked against GENESIS_HASH.

    The fix must not paper over a broken first entry by sourcing a predecessor
    that does not exist.
    """
    await _seed_chain(test_session, chain_tenant.id)

    verification = await AuditLogService(test_session).verify_chain(
        tenant_id=chain_tenant.id,
        start_sequence=1,
    )

    assert verification.entries_verified == CHAIN_LENGTH
    assert verification.is_valid is True


async def test_partial_verification_still_detects_real_tampering(test_session, chain_tenant):
    """Seeding the real predecessor must not turn the check into a rubber stamp.

    If the fix simply trusted ``entry.previous_hash``, every range would verify.
    Tamper with an in-range entry's payload and the entry-hash check must still
    fire.
    """
    entries = await _seed_chain(test_session, chain_tenant.id)

    tampered = entries[3]  # sequence 4, inside the range verified below
    tampered.new_values = {"step": "TAMPERED"}
    test_session.add(tampered)
    await test_session.commit()

    verification = await AuditLogService(test_session).verify_chain(
        tenant_id=chain_tenant.id,
        start_sequence=3,
    )

    assert verification.is_valid is False, "tampering inside a partial range went undetected"
    accused = {e["sequence"] for e in (verification.invalid_entries or [])}
    assert 4 in accused, f"expected sequence 4 to be flagged, got {verification.invalid_entries}"


async def test_range_starting_beyond_the_chain_is_not_reported_as_tampering(test_session, chain_tenant):
    """A start_sequence past the end of the chain selects nothing, which is not a mismatch."""
    await _seed_chain(test_session, chain_tenant.id)

    verification = await AuditLogService(test_session).verify_chain(
        tenant_id=chain_tenant.id,
        start_sequence=999,
    )

    assert verification.entries_verified == 0
    assert verification.is_valid is True


async def test_missing_predecessor_is_reported_distinctly_and_not_as_genesis(test_session, chain_tenant):
    """A hole below the range must be named, not silently treated as the chain's start.

    This is the contested-deletion case. If the entries below ``start_sequence``
    are gone, the first in-range entry's link cannot be checked against anything.
    Treating that as genesis would reproduce C-18; treating it as valid would
    hide a deletion from an append-only log. It gets its own error string so a
    reader can tell "unverifiable" from "broken".
    """
    from sqlalchemy import delete

    await _seed_chain(test_session, chain_tenant.id)

    # Remove sequences 1 and 2, leaving 3..5 with nothing before them.
    await test_session.execute(
        delete(AuditLogEntry).where(
            AuditLogEntry.tenant_id == chain_tenant.id,
            AuditLogEntry.sequence < 3,
        )
    )
    await test_session.commit()

    verification = await AuditLogService(test_session).verify_chain(
        tenant_id=chain_tenant.id,
        start_sequence=3,
    )

    assert verification.is_valid is False, "a hole below the range was reported as a clean chain"
    errors = {e["sequence"]: e["error"] for e in (verification.invalid_entries or [])}
    assert errors.get(3) == "Predecessor missing", (
        "expected sequence 3 to be reported as having no verifiable predecessor, " f"got {verification.invalid_entries}"
    )
    # The entries that do have predecessors in range must not be dragged in.
    assert 4 not in errors, f"sequence 4 has a verifiable predecessor and must not be flagged: {errors}"
    assert 5 not in errors, f"sequence 5 has a verifiable predecessor and must not be flagged: {errors}"
