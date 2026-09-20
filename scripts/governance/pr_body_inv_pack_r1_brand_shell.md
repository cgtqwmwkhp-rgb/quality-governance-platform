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

## 4) Acceptance Criteria (AC)
- [x] AC-01: A pack PDF embeds Inter (Type0) and the Plantexpand lockup image. It does not embed Helvetica as the body face.
- [x] AC-02: Passing `organisation_name="Default Organisation"` and `primary_color="#3B82F6"` does not print Default Organisation and does not use Tailwind blue as the letterhead.
- [x] AC-03: Cover carries Plantexpand Ltd, Unit 7 Buckingham Square, SS11 8YQ, 01268 204782, plantexpand.com, and UNCONTROLLED WHEN PRINTED.
- [x] AC-04: C1 redaction honesty notice still renders. Chronology remains withheld on external packs. C17 retain-on-issue still stores PDF bytes.
- [x] AC-05: Existing chronology/ICAM golden fixtures stay byte-identical (Helvetica figure path).

## 5) Testing Evidence
- [x] Unit — `tests/unit/test_investigation_pack_brand.py`, `test_investigation_pack_ir.py`, `test_investigation_pack_pdf.py`, `test_investigation_pack_draw.py`, `test_investigation_pack_issue.py` — 216 passed locally.
- [ ] Full CI — linked after PR checks.

## 6) Critical Journeys
- [x] CUJ-01: Quality lead downloads the PDF for REF-2026-0012 and sees Plantexpand letterhead, not a blue Default Organisation band.
- [x] CUJ-02: After C17 issue, a later download still returns the retained bytes from issue time.

## 7) Observability
- No new metrics. Fail-closed missing-asset and render errors surface as 500 on download/issue, same as today's fpdf2-missing path. Issued-pack download still uses `investigation_pack_retained_download_failed`.

## 8) Release Plan
- Merge when Ledger + All Checks Passed + Smoke Tests (CRITICAL) are green. C18 stays held. Azure is one SHA.
- After deploy: prod `build_sha` equals this merge SHA; download an unissued pack and confirm Inter + lockup + Plantexpand Ltd, not Default Organisation.

## 9) Rollback Plan
- **Owner:** David Harris
- **Rollback trigger:** a customer pack prints Default Organisation, Helvetica-only chrome, or a blue tenant band; issue 500s because Inter/lockup failed to ship in the image.
- **Rollback steps:** Revert the squash; redeploy C17 `ba30e005c50a`. Packs already issued under C17 keep their retained bytes.

## 10) Evidence Pack
- Kill SHA: `ba30e005c50a` (INV-C17 LIVE)
- Head at open: `ba30e005c50a`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Brand kit bundled; IR present; letterhead ignores tenant colour/name
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
