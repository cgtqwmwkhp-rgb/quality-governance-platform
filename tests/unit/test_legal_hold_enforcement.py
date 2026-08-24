"""WC-1 — the legal-hold guard fails closed rather than fails quiet.

The integration suite proves the guard is wired to the endpoints and refuses a
held write. What it cannot show is what happens when the guard *cannot answer*:
a hold register that will not read must refuse the write, not wave it through.
Those paths are asserted here because they are unreachable from HTTP without
breaking the database on purpose.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.domain.exceptions import BadRequestError, ConflictError
from src.domain.models.document import Document
from src.domain.services.document_version_service import assert_publisher_is_not_author
from src.domain.services.legal_hold_enforcement import (
    LEGAL_HOLD_ACTIVE,
    assert_controlled_document_not_held,
    assert_document_not_held,
    matter_reference_of,
)


class _ExplodingSession:
    """A session whose reads fail — i.e. hold state cannot be established."""

    def __init__(self) -> None:
        self.calls = 0

    async def scalar(self, *_args, **_kwargs):
        self.calls += 1
        raise RuntimeError("hold register unavailable")


class _EmptySession:
    async def scalar(self, *_args, **_kwargs):
        return None


def test_blank_matter_reference_is_not_a_hold_scope():
    """A stray empty string must read as "filed under no matter", not as a matter."""
    assert matter_reference_of(SimpleNamespace(legal_matter_reference=None)) is None
    assert matter_reference_of(SimpleNamespace(legal_matter_reference="")) is None
    assert matter_reference_of(SimpleNamespace(legal_matter_reference="   ")) is None
    assert matter_reference_of(SimpleNamespace(legal_matter_reference="  M-1 ")) == "M-1"
    assert matter_reference_of(SimpleNamespace()) is None


@pytest.mark.asyncio
async def test_unreadable_hold_register_refuses_the_write():
    """Fail closed: the error propagates, so the caller's transaction never commits."""
    document = Document(id=7, tenant_id=1, legal_matter_reference="MATTER-1")
    session = _ExplodingSession()

    with pytest.raises(RuntimeError, match="hold register unavailable"):
        await assert_document_not_held(session, document, action="revised")

    assert session.calls == 1, "the guard did not attempt to read hold state at all"


@pytest.mark.asyncio
async def test_a_document_with_no_tenant_is_refused_rather_than_guessed():
    """Reading another tenant's holds to answer this one would be worse than refusing."""
    document = SimpleNamespace(id=7, tenant_id=None, legal_matter_reference="MATTER-1")

    with pytest.raises(ConflictError) as excinfo:
        await assert_document_not_held(_EmptySession(), document, action="revised")
    assert excinfo.value.code == LEGAL_HOLD_ACTIVE


@pytest.mark.asyncio
async def test_a_document_filed_under_no_matter_is_not_frozen():
    """The open direction, asserted so "fail closed" is not read as "refuse always"."""
    document = Document(id=7, tenant_id=1, legal_matter_reference=None)
    await assert_document_not_held(_ExplodingSession(), document, action="revised")


@pytest.mark.asyncio
async def test_an_unanchored_control_record_is_outside_document_hold_scope():
    """Hold scope lives on the Register row, so a shell with no anchor has none.

    WC-1 stops new unanchored control records being created; the ones that predate
    it cannot be frozen through a document that does not exist, and inventing a
    refusal here would freeze every legacy shell permanently.
    """
    controlled = SimpleNamespace(id=3, library_document_id=None)
    await assert_controlled_document_not_held(_ExplodingSession(), controlled, tenant_id=1, action="revised")


def test_an_author_may_not_publish_their_own_document():
    document = SimpleNamespace(id=11, created_by_id=5)

    with pytest.raises(BadRequestError) as excinfo:
        assert_publisher_is_not_author(document, published_by_id=5)
    assert excinfo.value.code == "SEPARATION_OF_DUTIES"

    assert_publisher_is_not_author(document, published_by_id=6)


def test_an_unattributed_publish_is_not_treated_as_self_publication():
    """With no identity on one side there is no separation to enforce.

    Refusing here would block publishing every pre-attribution row rather than
    enforcing a separation of duties, which is a different (and wrong) control.
    """
    assert_publisher_is_not_author(SimpleNamespace(id=11, created_by_id=None), published_by_id=5)
    assert_publisher_is_not_author(SimpleNamespace(id=11, created_by_id=5), published_by_id=None)
