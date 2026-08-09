"""Governance Library WA-2 — an allocated PEL reference is never rewritten.

ADR-0023: the reference is printed on the document face and cited in client
audit packs, so a mis-filed one is corrected by re-filing (new reference, old
one retired), never by editing in place. The same holds for the function it
was drawn from — rewriting that would leave the reference describing a
function the document no longer claims.

Two layers enforce this. These tests cover the ORM layer in
``src.domain.models.document``, which is what any code path going through a
SQLAlchemy session hits. The authoritative layer is the PostgreSQL trigger
``trg_documents_pel_doc_ref_immutable`` installed by
``alembic/versions/20261025_lib_wa2_functions_pel.py``, which also catches raw
SQL; it cannot be exercised on SQLite and is verified when the migration
applies.
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import ConflictError
from src.domain.models.document import Document


def _document() -> Document:
    return Document(title="Wheel Torque Policy", reference_number="DOC-2026-0001")


class TestPelDocRefImmutability:
    def test_allocating_a_reference_on_a_fresh_document_is_allowed(self):
        doc = _document()
        doc.pel_doc_ref = "PEL-TECH-0001"
        assert doc.pel_doc_ref == "PEL-TECH-0001"

    def test_setting_the_same_reference_again_is_a_no_op(self):
        """Re-assignment during a refresh/merge must not be mistaken for a rewrite."""
        doc = _document()
        doc.pel_doc_ref = "PEL-TECH-0001"
        doc.pel_doc_ref = "PEL-TECH-0001"
        assert doc.pel_doc_ref == "PEL-TECH-0001"

    def test_rewriting_an_allocated_reference_raises(self):
        doc = _document()
        doc.pel_doc_ref = "PEL-TECH-0001"
        with pytest.raises(ConflictError) as exc:
            doc.pel_doc_ref = "PEL-HSEQ-0002"
        assert exc.value.code == "PEL_REF_IMMUTABLE"
        assert doc.pel_doc_ref == "PEL-TECH-0001"

    def test_clearing_an_allocated_reference_raises(self):
        """Nulling it is a rewrite too — the reference would be freed while still cited."""
        doc = _document()
        doc.pel_doc_ref = "PEL-TECH-0001"
        with pytest.raises(ConflictError):
            doc.pel_doc_ref = None
        assert doc.pel_doc_ref == "PEL-TECH-0001"


class TestFunctionImmutability:
    def test_setting_the_function_on_a_fresh_document_is_allowed(self):
        doc = _document()
        doc.function_id = 8
        assert doc.function_id == 8

    def test_reassigning_the_function_raises(self):
        doc = _document()
        doc.function_id = 8
        with pytest.raises(ConflictError) as exc:
            doc.function_id = 1
        assert exc.value.code == "PEL_REF_IMMUTABLE"
        assert doc.function_id == 8

    def test_clearing_the_function_raises(self):
        doc = _document()
        doc.function_id = 8
        with pytest.raises(ConflictError):
            doc.function_id = None
        assert doc.function_id == 8

    def test_ownership_moving_does_not_touch_an_issued_reference(self):
        """ADR-0023: reassigning who owns information security leaves PEL-IT-#### standing."""
        doc = _document()
        doc.function_id = 2
        doc.pel_doc_ref = "PEL-IT-0014"

        with pytest.raises(ConflictError):
            doc.function_id = 9  # ownership moves IT -> DP

        assert doc.pel_doc_ref == "PEL-IT-0014"
        assert doc.function_id == 2


class TestOtherFieldsRemainMutable:
    def test_title_and_category_are_not_frozen_by_the_guard(self):
        """Only the reference axis is immutable — re-classifying a document stays possible."""
        doc = _document()
        doc.pel_doc_ref = "PEL-TECH-0001"
        doc.title = "Wheel Torque Policy (rev B)"
        doc.category_id = 5
        doc.category_id = 6
        assert doc.title == "Wheel Torque Policy (rev B)"
        assert doc.category_id == 6
