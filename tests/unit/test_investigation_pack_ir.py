"""Pack document IR — cover/contents derive from the document, not the tenant."""

from __future__ import annotations

from dataclasses import fields

from src.domain.services.investigation_pack_ir import DocumentMeta, PackDocument, Paragraph, Section


def test_document_meta_has_no_tenant_fields() -> None:
    names = {item.name for item in fields(DocumentMeta)}
    assert "organisation_name" not in names
    assert "primary_color" not in names
    assert "tenant_id" not in names


def test_contents_derive_from_in_contents_sections() -> None:
    meta = DocumentMeta(
        reference="REF-1",
        title="T",
        audience_label="Internal customer pack",
        status_label="Open",
        level_label="High",
        generated_at_label="8 September 2026",
        pack_uuid="x",
        content_sha256="y",
        classification="UNCONTROLLED WHEN PRINTED",
        confidentiality="",
    )
    document = PackDocument(
        meta=meta,
        sections=(
            Section(id="a", heading="Incident details", blocks=(Paragraph("one"),), in_contents=True),
            Section(id="hidden", heading="Internal", blocks=(), in_contents=False),
            Section(id="b", heading="Findings", blocks=(), in_contents=True),
        ),
    )
    assert document.contents_entries() == ((1, "Incident details"), (2, "Findings"))


def test_blocks_are_frozen() -> None:
    para = Paragraph("hello")
    try:
        para.text = "no"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Paragraph must be frozen")
