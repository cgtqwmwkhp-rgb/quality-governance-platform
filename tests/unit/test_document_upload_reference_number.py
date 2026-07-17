"""Library upload must assign a document reference number before response validation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.reference_number import ReferenceNumberService


@pytest.mark.asyncio
async def test_document_prefix_is_doc():
    mock_db = AsyncMock()
    with patch.object(ReferenceNumberService, "_next_sequence", new_callable=AsyncMock, return_value=3):
        ref = await ReferenceNumberService.generate(mock_db, "document", MagicMock(), year=2026)
    assert ref == "DOC-2026-0003"


@pytest.mark.asyncio
async def test_upload_document_sets_generated_reference_number():
    """Ensure upload path wires ReferenceNumberService into the Document constructor."""
    from src.api.routes import documents as documents_route

    generated = "DOC-2026-0009"
    captured: dict = {}

    class _FakeDoc:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.id = 99
            self.reference_number = kwargs.get("reference_number")
            self.title = kwargs["title"]
            self.status = MagicMock(value="processing")

    user = MagicMock()
    user.tenant_id = 1
    user.id = 5

    file = MagicMock()
    file.filename = "policy.pdf"
    file.content_type = "application/pdf"
    file.read = AsyncMock(return_value=b"%PDF-1.4 fake")

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()

    with (
        patch.object(ReferenceNumberService, "generate", new_callable=AsyncMock, return_value=generated) as gen,
        patch.object(documents_route, "Document", side_effect=_FakeDoc),
        patch.object(documents_route, "document_version_service") as dvs,
        patch.object(documents_route, "storage_service") as storage,
        patch.object(documents_route, "_process_uploaded_document", new_callable=AsyncMock),
        patch.object(documents_route, "track_metric"),
    ):
        dvs.build_initial_library_version.return_value = MagicMock()
        storage.return_value.upload = AsyncMock()

        response = await documents_route.upload_document(
            db=db,
            current_user=user,
            file=file,
            title="Policy",
            description=None,
            document_type="other",
            category=None,
            department=None,
            sensitivity="internal",
        )

    gen.assert_awaited_once()
    assert captured["reference_number"] == generated
    assert response.reference_number == generated
    assert response.id == 99
