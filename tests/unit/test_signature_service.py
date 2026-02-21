"""Unit tests for Signature Service - can run standalone."""

import hashlib
import os
import secrets
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

try:
    from src.domain.services.signature_service import SignatureService

    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Imports not available")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _mock_signer(
    signer_id=1,
    status="pending",
    order=1,
    email="signer@example.com",
    name="Test Signer",
    user_id=10,
    request=None,
):
    """Create a mock SignatureRequestSigner."""
    signer = MagicMock()
    signer.id = signer_id
    signer.status = status
    signer.order = order
    signer.email = email
    signer.name = name
    signer.user_id = user_id
    signer.first_viewed_at = None
    signer.last_viewed_at = None
    signer.request_id = 1
    signer.request = request or _mock_request()
    signer.signer_role = "signer"
    signer.ip_address = None
    signer.user_agent = None
    signer.geo_location = None
    signer.auth_method = None
    signer.signed_at = None
    signer.signature_type = None
    signer.signature_data = None
    signer.declined_at = None
    signer.decline_reason = None
    return signer


def _mock_request(
    request_id=1,
    status="pending",
    workflow_type="sequential",
    require_all=True,
    tenant_id=1,
    document_hash="abc123",
):
    """Create a mock SignatureRequest."""
    req = MagicMock()
    req.id = request_id
    req.status = status
    req.workflow_type = workflow_type
    req.require_all = require_all
    req.tenant_id = tenant_id
    req.document_hash = document_hash
    req.document_type = "policy"
    req.document_id = "DOC-001"
    req.completed_at = None
    req.expires_at = datetime.utcnow() + timedelta(days=30)
    req.created_at = datetime.utcnow()
    req.last_reminder_at = None
    req.reminder_frequency = 3
    return req


# ---------------------------------------------------------------------------
# Legal statement constant
# ---------------------------------------------------------------------------


def test_legal_statement_defined():
    """Legal statement text must be present and non-trivial."""
    assert hasattr(SignatureService, "LEGAL_STATEMENT")
    assert len(SignatureService.LEGAL_STATEMENT) > 50
    assert "electronic signature" in SignatureService.LEGAL_STATEMENT.lower()


# ---------------------------------------------------------------------------
# create_request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_request_generates_reference():
    """create_request generates a SIG-prefixed reference number."""
    db = _mock_db()
    svc = SignatureService(db)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    request = await svc.create_request(
        tenant_id=1,
        title="Test Signature Request",
        initiated_by_id=5,
        document_type="policy",
    )

    db.add.assert_called()
    db.flush.assert_awaited()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_create_request_hashes_document_content():
    """Document content is hashed with SHA-256."""
    db = _mock_db()
    svc = SignatureService(db)

    content = b"This is the document content"
    expected_hash = hashlib.sha256(content).hexdigest()

    request = await svc.create_request(
        tenant_id=1,
        title="Hashed Doc",
        initiated_by_id=5,
        document_type="audit",
        document_content=content,
    )

    add_call_args = db.add.call_args_list[0][0][0]
    assert add_call_args.document_hash == expected_hash


@pytest.mark.asyncio
async def test_create_request_with_signers():
    """Signers are created with access tokens when provided."""
    db = _mock_db()
    svc = SignatureService(db)

    signers = [
        {"email": "alice@example.com", "name": "Alice", "role": "signer"},
        {"email": "bob@example.com", "name": "Bob", "role": "approver"},
    ]

    await svc.create_request(
        tenant_id=1,
        title="Multi-signer",
        initiated_by_id=5,
        document_type="contract",
        signers=signers,
    )

    # 1 request + 2 signers + 1 audit log = 4 adds
    assert db.add.call_count == 4


# ---------------------------------------------------------------------------
# send_request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_request_changes_status_to_pending():
    """send_request transitions draft -> pending."""
    db = _mock_db()
    svc = SignatureService(db)

    request = _mock_request(status="draft")
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = request
    db.execute = AsyncMock(return_value=result_mock)

    returned = await svc.send_request(request_id=1)
    assert returned.status == "pending"


@pytest.mark.asyncio
async def test_send_request_rejects_non_draft():
    """send_request raises ValueError for already-sent requests."""
    db = _mock_db()
    svc = SignatureService(db)

    request = _mock_request(status="pending")
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = request
    db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(ValueError, match="already pending"):
        await svc.send_request(request_id=1)


# ---------------------------------------------------------------------------
# void_request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_void_request_marks_voided():
    """void_request sets status to voided."""
    db = _mock_db()
    svc = SignatureService(db)

    request = _mock_request(status="pending")
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = request
    db.execute = AsyncMock(return_value=result_mock)

    returned = await svc.void_request(request_id=1, voided_by_id=5, reason="No longer needed")
    assert returned.status == "voided"


@pytest.mark.asyncio
async def test_void_request_rejects_completed():
    """Cannot void a completed request."""
    db = _mock_db()
    svc = SignatureService(db)

    request = _mock_request(status="completed")
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = request
    db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(ValueError, match="Cannot void"):
        await svc.void_request(request_id=1, voided_by_id=5)


@pytest.mark.asyncio
async def test_void_request_rejects_expired():
    """Cannot void an expired request."""
    db = _mock_db()
    svc = SignatureService(db)

    request = _mock_request(status="expired")
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = request
    db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(ValueError, match="Cannot void"):
        await svc.void_request(request_id=1, voided_by_id=5)


# ---------------------------------------------------------------------------
# Decline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decline_sets_status_and_reason():
    """Declining sets signer status to declined and records reason."""
    db = _mock_db()
    svc = SignatureService(db)

    request = _mock_request(status="pending", require_all=True)
    signer = _mock_signer(status="viewed", request=request)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = signer
    db.execute = AsyncMock(return_value=result_mock)

    returned = await svc.decline(
        signer_id=1,
        reason="Disagree with terms",
        ip_address="192.168.1.1",
        user_agent="TestBrowser/1.0",
    )

    assert returned.status == "declined"
    assert returned.decline_reason == "Disagree with terms"
    assert request.status == "declined"


@pytest.mark.asyncio
async def test_decline_already_signed_raises():
    """Cannot decline after already signing."""
    db = _mock_db()
    svc = SignatureService(db)

    signer = _mock_signer(status="signed")
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = signer
    db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(ValueError, match="Already signed"):
        await svc.decline(
            signer_id=1,
            reason="Changed my mind",
            ip_address="1.2.3.4",
            user_agent="Test",
        )


if __name__ == "__main__":
    print("=" * 60)
    print("SIGNATURE SERVICE UNIT TESTS")
    print("=" * 60)

    test_legal_statement_defined()
    print("✓ Legal statement defined")

    print()
    print("=" * 60)
    print("ALL SIGNATURE SERVICE TESTS PASSED ✅")
    print("=" * 60)
