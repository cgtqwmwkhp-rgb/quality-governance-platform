"""Northern Star W6 / NS-WF — issue state machine and issue-time hard blocks.

Covers the transition table projected from the authority pack, plus R07, R10,
R11, R12, R14 (approval leg), R18, R20, R22 and R23. Rules the wave did not
land are asserted as *gaps* at the bottom of this file so the deferral is
visible in CI rather than only in a PR body.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import BadRequestError, StateTransitionError, ValidationError
from src.domain.models.enums import DocumentStatus
from src.domain.services.document_library_lifecycle_service import approve_document, issue_document
from src.domain.services.library_workflow import (
    PROCEDURAL_ROUTES,
    RULE_WF_IDS,
    assert_amendment_record_complete,
    assert_approver_is_not_version_author,
    assert_parent_named,
    assert_review_cycle_declared,
    assert_transition_allowed,
    assert_whole_number_version,
    canonical_status,
    transition_is_allowed,
    transition_table,
)

_RULES_PATH = Path(__file__).resolve().parents[2] / "specs" / "governance-library" / "northern-star-rules-v6.json"


# ---------------------------------------------------------------------------
# Transition table — projected from the pack, not re-typed
# ---------------------------------------------------------------------------


def test_table_carries_every_mappable_pack_row():
    """Every pack row that names two states is in the table; the rest are named routes."""
    pack = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    rows = pack["workflow_transitions"]
    dropped = [r for r in rows if str(r["to"]).strip().lower() in PROCEDURAL_ROUTES or str(r["from"]).lower() == "any"]

    assert len(transition_table()) == len(rows) - len(dropped)
    assert {str(r["to"]).strip().lower() for r in dropped} <= PROCEDURAL_ROUTES | {"level change"}


@pytest.mark.parametrize(
    "source,target",
    [
        (DocumentStatus.DRAFT, DocumentStatus.UNDER_REVIEW),
        (DocumentStatus.UNDER_REVIEW, DocumentStatus.DRAFT),
        (DocumentStatus.UNDER_REVIEW, DocumentStatus.APPROVED),
        (DocumentStatus.APPROVED, DocumentStatus.PUBLISHED),
        (DocumentStatus.PUBLISHED, DocumentStatus.SUPERSEDED),
        (DocumentStatus.PUBLISHED, DocumentStatus.RETIRED),
        (DocumentStatus.DRAFT, DocumentStatus.RETIRED),
    ],
)
def test_pack_transitions_are_allowed(source, target):
    assert transition_is_allowed(source, target) is True


@pytest.mark.parametrize(
    "source,target",
    [
        # The move this wave exists to refuse: live without an approval.
        (DocumentStatus.DRAFT, DocumentStatus.PUBLISHED),
        (DocumentStatus.UNDER_REVIEW, DocumentStatus.PUBLISHED),
        (DocumentStatus.APPROVED, DocumentStatus.UNDER_REVIEW),
        (DocumentStatus.PUBLISHED, DocumentStatus.APPROVED),
        (DocumentStatus.SUPERSEDED, DocumentStatus.PUBLISHED),
        (DocumentStatus.RETIRED, DocumentStatus.DRAFT),
        (DocumentStatus.APPROVED, DocumentStatus.APPROVED),
    ],
)
def test_illegal_moves_are_refused(source, target):
    assert transition_is_allowed(source, target) is False
    with pytest.raises(StateTransitionError):
        assert_transition_allowed(source, target)


def test_indexed_and_rejected_are_the_draft_state():
    """Both were submittable before the table existed; the alias records that once."""
    assert canonical_status(DocumentStatus.INDEXED) is DocumentStatus.DRAFT
    assert canonical_status(DocumentStatus.REJECTED) is DocumentStatus.DRAFT
    assert transition_is_allowed(DocumentStatus.INDEXED, DocumentStatus.UNDER_REVIEW) is True
    assert transition_is_allowed(DocumentStatus.REJECTED, DocumentStatus.UNDER_REVIEW) is True


def test_under_revision_is_not_silently_widened_into_draft():
    """It was not submittable before this wave and this wave does not decide that."""
    assert canonical_status(DocumentStatus.UNDER_REVISION) is DocumentStatus.UNDER_REVISION
    assert transition_is_allowed(DocumentStatus.UNDER_REVISION, DocumentStatus.UNDER_REVIEW) is False


def test_unknown_and_missing_statuses_fail_closed():
    assert canonical_status(None) is None
    assert canonical_status("not-a-status") is None
    assert transition_is_allowed(None, DocumentStatus.PUBLISHED) is False
    assert transition_is_allowed("not-a-status", DocumentStatus.PUBLISHED) is False


def test_string_statuses_project_onto_the_table():
    """Serialized statuses off the wire must not slip past the table."""
    assert transition_is_allowed("approved", DocumentStatus.PUBLISHED) is True
    assert transition_is_allowed("draft", DocumentStatus.PUBLISHED) is False


# ---------------------------------------------------------------------------
# R22 — whole number versions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("version_number", ["1", "2", "2.0", "10.00", " 3 "])
def test_r22_accepts_whole_numbers(version_number):
    assert_whole_number_version(version_number)


@pytest.mark.parametrize("version_number", ["1.1", "0", "0.0", "2.01", "", None, "v2", "1.0.1"])
def test_r22_refuses_drafts_and_junk(version_number):
    with pytest.raises(ValidationError, match="R22"):
        assert_whole_number_version(version_number)


# ---------------------------------------------------------------------------
# R23 — approver is not the author of the version
# ---------------------------------------------------------------------------


def test_r23_refuses_the_version_author_as_approver():
    with pytest.raises(ValidationError, match="R23"):
        assert_approver_is_not_version_author(approver_id=7, version_author_id=7)


def test_r23_allows_a_second_person():
    assert_approver_is_not_version_author(approver_id=7, version_author_id=8)


def test_r23_skips_unattributed_rows_rather_than_blocking_them():
    """No identity to compare is not a separation of duties failure."""
    assert_approver_is_not_version_author(approver_id=None, version_author_id=7)
    assert_approver_is_not_version_author(approver_id=7, version_author_id=None)


@pytest.mark.asyncio
async def test_approve_refuses_the_author_of_the_version_even_when_someone_else_filed_it():
    """The gap the old document-level check left open: self-approving a revision."""
    document = SimpleNamespace(
        id=1,
        tenant_id=1,
        status=DocumentStatus.UNDER_REVIEW,
        created_by_id=99,  # filed by someone else years ago
        category_id=None,
        pel_doc_ref=None,
        version="1.0",
        file_name="a.pdf",
        file_path="x",
        file_size=1,
        legal_matter_reference=None,
    )
    version = SimpleNamespace(
        id=9,
        status="draft",
        is_immutable=False,
        version_number="2.0",
        change_notes="Revision 2",
        created_by_id=5,
        file_name="a.pdf",
        file_path="x",
        file_size=1,
    )

    with pytest.raises(ValidationError, match="R23"):
        await approve_document(_db(version), document, approved_by_id=5)


# ---------------------------------------------------------------------------
# R10 / R11 — amendment record complete and reconciling
# ---------------------------------------------------------------------------


def test_r10_requires_a_change_note_on_the_amendment_row():
    with pytest.raises(ValidationError, match="R10"):
        assert_amendment_record_complete(change_notes="   ", version_number="2.0", document_version="2.0")


def test_r11_requires_the_row_to_be_the_version_the_document_claims():
    with pytest.raises(ValidationError, match="R11"):
        assert_amendment_record_complete(change_notes="Reissue", version_number="2.0", document_version="3.0")


def test_r10_r11_pass_when_the_row_is_complete_and_reconciles():
    assert_amendment_record_complete(change_notes="Reissue", version_number="2.0", document_version="2.0")


# ---------------------------------------------------------------------------
# R20 — review cycle and its basis
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "months,basis",
    [
        (None, "Statutory — Fire Safety Order"),
        (12, None),
        (12, "  "),
        (0, "Statutory"),
        (-3, "Statutory"),
        (None, None),
    ],
)
def test_r20_refuses_an_unstated_cycle_or_basis(months, basis):
    with pytest.raises(ValidationError, match="R20"):
        assert_review_cycle_declared(review_cycle_months=months, review_cycle_basis=basis)


def test_r20_passes_when_both_are_stated():
    assert_review_cycle_declared(review_cycle_months=12, review_cycle_basis="Statutory — Fire Safety Order 2005")


# ---------------------------------------------------------------------------
# R07 — every document below L1 names a parent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cascade_level", [None, 1])
def test_r07_does_not_apply_at_l1_or_above_the_cascade(cascade_level):
    assert_parent_named(cascade_level=cascade_level, has_primary_parent=False)


@pytest.mark.parametrize("cascade_level", [2, 3, 4, 5])
def test_r07_blocks_an_orphan_below_l1(cascade_level):
    with pytest.raises(ValidationError, match="R07"):
        assert_parent_named(cascade_level=cascade_level, has_primary_parent=False)


@pytest.mark.parametrize("cascade_level", [2, 5])
def test_r07_passes_when_a_parent_is_named(cascade_level):
    assert_parent_named(cascade_level=cascade_level, has_primary_parent=True)


# ---------------------------------------------------------------------------
# The issue transition end to end (fake session)
# ---------------------------------------------------------------------------


def _db(scalar_result, *, execute_rows: list | None = None):
    """Async-session double: `scalar` returns a fixed row, `execute` a row list."""
    return SimpleNamespace(
        scalar=AsyncMock(return_value=scalar_result),
        execute=AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=execute_rows or [])))
            )
        ),
        get=AsyncMock(return_value=None),
        flush=AsyncMock(),
    )


def _issuable_document(**overrides):
    base = dict(
        id=1,
        tenant_id=1,
        status=DocumentStatus.APPROVED,
        version="2.0",
        cascade_level=1,
        review_cycle_months=12,
        review_cycle_basis="Statutory — Fire Safety Order 2005",
        pel_doc_ref=None,
        legal_matter_reference=None,
        file_name="a.pdf",
        file_path="x",
        file_size=1,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _approved_version(**overrides):
    base = dict(
        id=9,
        status="approved",
        is_immutable=True,
        version_number="2.0",
        change_notes="Reissue after annual review",
        created_by_id=5,
        published_by_id=6,
        published_at=None,
        issued_at=None,
        issued_by_id=None,
        file_name="a.pdf",
        file_path="x",
        file_size=1,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_issue_moves_an_approved_document_live_and_records_the_issuer():
    document = _issuable_document()
    version = _approved_version()

    issued = await issue_document(_db(version), document, issued_by_id=4)

    assert document.status == DocumentStatus.PUBLISHED
    assert issued.status == "published"
    assert issued.is_immutable is True
    assert issued.issued_by_id == 4
    assert issued.issued_at is not None
    # The approval record survives the issue.
    assert issued.published_by_id == 6


@pytest.mark.asyncio
async def test_issue_refuses_a_document_that_was_never_approved():
    """R14's approval leg — the whole point of a separate issue transition."""
    document = _issuable_document(status=DocumentStatus.DRAFT)
    with pytest.raises(StateTransitionError):
        await issue_document(_db(_approved_version()), document, issued_by_id=4)
    assert document.status == DocumentStatus.DRAFT


@pytest.mark.asyncio
async def test_issue_refuses_when_no_approved_version_row_exists():
    document = _issuable_document()
    with pytest.raises(BadRequestError, match="R14"):
        await issue_document(_db(None), document, issued_by_id=4)
    assert document.status == DocumentStatus.APPROVED


@pytest.mark.asyncio
async def test_issue_refuses_an_explicitly_named_version_that_is_still_a_draft():
    """`version_id` must not be a way around the approval."""
    document = _issuable_document()
    draft = _approved_version(status="draft", is_immutable=False)
    with pytest.raises(BadRequestError, match="R14"):
        await issue_document(_db(draft), document, issued_by_id=4, version_id=draft.id)


@pytest.mark.asyncio
async def test_issue_refuses_a_decimal_version():
    document = _issuable_document(version="2.1")
    with pytest.raises(ValidationError, match="R22"):
        await issue_document(_db(_approved_version(version_number="2.1")), document, issued_by_id=4)


@pytest.mark.asyncio
async def test_issue_refuses_a_self_approved_version():
    document = _issuable_document()
    version = _approved_version(created_by_id=6, published_by_id=6)
    with pytest.raises(ValidationError, match="R23"):
        await issue_document(_db(version), document, issued_by_id=4)


@pytest.mark.asyncio
async def test_issue_refuses_an_empty_amendment_record():
    document = _issuable_document()
    with pytest.raises(ValidationError, match="R10"):
        await issue_document(_db(_approved_version(change_notes=None)), document, issued_by_id=4)


@pytest.mark.asyncio
async def test_issue_refuses_an_unstated_review_cycle():
    document = _issuable_document(review_cycle_months=None, review_cycle_basis=None)
    with pytest.raises(ValidationError, match="R20"):
        await issue_document(_db(_approved_version()), document, issued_by_id=4)


@pytest.mark.asyncio
async def test_issue_accepts_the_review_cycle_stated_on_the_request():
    document = _issuable_document(review_cycle_months=None, review_cycle_basis=None)
    await issue_document(
        _db(_approved_version()),
        document,
        issued_by_id=4,
        review_cycle_months=24,
        review_cycle_basis="ISO 9001 certification expectation",
    )
    assert document.review_cycle_months == 24
    assert document.status == DocumentStatus.PUBLISHED


@pytest.mark.asyncio
async def test_issue_never_invents_a_review_cycle():
    """A partial statement is still unstated — nothing is defaulted in."""
    document = _issuable_document(review_cycle_months=None, review_cycle_basis=None)
    with pytest.raises(ValidationError, match="R20"):
        await issue_document(_db(_approved_version()), document, issued_by_id=4, review_cycle_months=24)
    assert document.review_cycle_basis is None


@pytest.mark.asyncio
async def test_issue_blocks_an_orphan_below_l1(monkeypatch):
    monkeypatch.setattr(
        "src.domain.services.document_library_lifecycle_service.has_confirmed_primary_parent",
        AsyncMock(return_value=False),
    )
    document = _issuable_document(cascade_level=3)
    with pytest.raises(ValidationError, match="R07"):
        await issue_document(_db(_approved_version()), document, issued_by_id=4)
    assert document.status == DocumentStatus.APPROVED


@pytest.mark.asyncio
async def test_issue_allows_a_child_that_names_a_parent(monkeypatch):
    monkeypatch.setattr(
        "src.domain.services.document_library_lifecycle_service.has_confirmed_primary_parent",
        AsyncMock(return_value=True),
    )
    document = _issuable_document(cascade_level=3)
    await issue_document(_db(_approved_version()), document, issued_by_id=4)
    assert document.status == DocumentStatus.PUBLISHED


@pytest.mark.asyncio
async def test_issue_supersedes_the_previous_issue_in_the_same_transaction():
    """R18 — not a nightly sweep that can miss the day."""
    document = _issuable_document()
    version = _approved_version()
    prior = SimpleNamespace(id=8, status="published", is_immutable=True)

    await issue_document(_db(version, execute_rows=[prior]), document, issued_by_id=4)

    assert prior.status == "superseded"
    assert prior.is_immutable is True


@pytest.mark.asyncio
async def test_issue_is_refused_under_a_legal_hold(monkeypatch):
    """The hold check must not be reachable only after the rule blocks pass."""
    from src.domain.exceptions import ConflictError

    async def _held(_db_arg, _document, *, action):
        raise ConflictError(f"held ({action})")

    monkeypatch.setattr(
        "src.domain.services.document_library_lifecycle_service.assert_document_not_held",
        _held,
    )
    document = _issuable_document(review_cycle_months=None)
    with pytest.raises(ConflictError, match="issued"):
        await issue_document(_db(_approved_version()), document, issued_by_id=4)


# ---------------------------------------------------------------------------
# R12 — amendment rows immutable (already enforced; pinned here)
# ---------------------------------------------------------------------------


def test_r12_issued_amendment_rows_are_read_only():
    from src.domain.services.document_version_service import assert_version_mutable, version_is_immutable

    assert version_is_immutable("published") is True
    assert version_is_immutable("superseded") is True
    assert version_is_immutable("approved") is True
    with pytest.raises(BadRequestError):
        assert_version_mutable("published", True)


# ---------------------------------------------------------------------------
# Honest gaps — asserted so the deferral cannot rot silently
# ---------------------------------------------------------------------------


def test_wave_declares_exactly_the_rules_it_touched():
    assert RULE_WF_IDS == {"R07", "R10", "R11", "R12", "R14", "R18", "R20", "R22", "R23"}


def test_r15_footer_stamping_is_not_implemented_and_is_not_claimed():
    """No rendering pipeline exists, so nothing stamps the level into a footer.

    This asserts the *absence*: if a renderer lands, this test fails and whoever
    lands it must say so rather than letting `issue` quietly imply a rendition.
    """
    import src.domain.services.library_workflow as workflow

    assert "R15" not in RULE_WF_IDS
    assert not hasattr(workflow, "assert_level_stamped_in_footer")


def test_the_legacy_publish_path_still_reaches_live_without_an_approval():
    """Documented gap: `/publish` is not the Northern Star issue transition.

    `publish_library` refuses a self-publish but has no approval precondition, so
    R14 is only enforced on the `/issue` path this wave added. Closing `/publish`
    is a product decision — an existing test asserts publishing must not invent
    an approval — so it is recorded here rather than quietly changed.
    """
    import inspect

    from src.domain.services.document_version_service import DocumentVersionService

    source = inspect.getsource(DocumentVersionService.publish_library)
    assert "assert_transition_allowed" not in source
