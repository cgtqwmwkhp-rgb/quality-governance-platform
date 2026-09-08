# Change Ledger (CL-INV-PACK-R1-BRAND-SHELL)

> Adjacent, not fixed here: R2 editorial layout (01–09 tables, UK dates in
> the body, Why 1–5, ICAM without ellipsis). R3 Word working copy from the
> same IR. C18 leftover-reader contraction stays held. Kill SHA is C17 LIVE
> `ba30e005c50a`. Azure stays one merge SHA.

## 1) Summary
- **Feature / Change name:** INV-PACK-R1 — Plantexpand letterhead on the investigation pack PDF
- **User goal:** The customer PDF must look like the Plantexpand investigation-report template (lockup, Inter, Jet Grey / Crimson, cover, legal address). It must not look like a blue Helvetica dump headed Default Organisation.
- **In scope:** bundled Inter (OFL) + lockup PNG; document IR; fpdf2 writer cover / contents / running footer; letterhead is the brand kit, not `tenants.name` / `tenants.primary_color`; unit tests. C17 retain-on-issue still PDF-only.
- **Out of scope:** R2 editorial restyle of findings/CAPA/ICAM; Word `.docx`; C18; Entra; PAMS; size-limit raise; new `en.json` keys.
- **Feature flag / kill switch:** None. Kill SHA = C17 LIVE `ba30e005c50a`.

## 2) Impact Map (what changed)
- **Database:** none.
- **Migration:** none.
- **Backend:** `investigation_pack_brand.py`, `investigation_pack_ir.py`, `investigation_pack_pdf_writer.py`, assets under `src/domain/services/pack_brand/`. `InvestigationPackPdfService.build_pdf_bytes` draws the kit letterhead. `render_pack_pdf` no longer takes tenant branding. Download and issue render paths drop the Tenant colour query.
- **Frontend:** none.
- **APIs:** none (PDF bytes change; routes unchanged).
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Unissued packs live-render with the new letterhead. Packs already issued under C17 keep their retained bytes — a renderer change cannot rewrite a disclosure.
- **Fail closed:** missing Inter or lockup raises `RuntimeError` / `BrandAssetError`. No Helvetica fallback (that would freeze an off-brand pack at issue). Uncovered glyphs become `?`, they do not vanish.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** No new fields. The pack still reproduces narrative as written (C1).
- **Lawful basis / retention:** unchanged. Issued PDF retention is still C17.
- **New processor?** No. **Entra?** Untouched, flag stays false.
- **Authorisation:** unchanged (`investigation:update` download / issue).

## Acceptance
- **AC-01:** A pack PDF embeds Inter (Type0) and the Plantexpand lockup image. It does not embed Helvetica as the body face.
- **AC-02:** Passing `organisation_name="Default Organisation"` and `primary_color="#3B82F6"` does not print Default Organisation and does not use Tailwind blue as the letterhead.
- **AC-03:** Cover carries Plantexpand Ltd, Unit 7 Buckingham Square, SS11 8YQ, 01268 204782, plantexpand.com, and UNCONTROLLED WHEN PRINTED.
- **AC-04:** C1 redaction honesty notice still renders. Chronology remains withheld on external packs. C17 retain-on-issue still stores PDF bytes.
- **AC-05:** Existing chronology/ICAM golden fixtures stay byte-identical (Helvetica figure path).

## CUJ
- **CUJ-01:** Quality lead downloads the PDF for REF-2026-0012 and sees Plantexpand letterhead, not a blue Default Organisation band.
- **CUJ-02:** After C17 issue, a later download still returns the retained bytes from issue time.

## Tests run
- `pytest tests/unit/test_investigation_pack_brand.py tests/unit/test_investigation_pack_ir.py tests/unit/test_investigation_pack_pdf.py tests/unit/test_investigation_pack_draw.py tests/unit/test_investigation_pack_issue.py` — 216 passed.

## Size
- counted lines: implementation + tests (lockup PNG, Inter TTFs, OFL.txt excluded as fixtures/assets).
