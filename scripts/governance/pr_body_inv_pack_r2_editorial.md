# Change Ledger (CL-INV-PACK-R2-EDITORIAL)

> Adjacent, not fixed here: R3 Word working copy from the same IR. C18 leftover-reader
> contraction stays held. Kill SHA is PACK-R1 LIVE `a989c16491d7`. Azure stays one
> merge SHA. Same stored pack payload — no invented narrative.

## 1) Summary
- **Feature / Change name:** INV-PACK-R2 — editorial layout on the investigation pack PDF
- **User goal:** The customer PDF must read like the Plantexpand investigation-report template: numbered 01–09 matching contents, definition tables, UK dates in the body, Why 1–5 without a fake "Why: Not recorded" field, ICAM wording wrapped rather than ellipsized.
- **In scope:** catalogue titles and chapter numbers aligned with contents; KeyValue / CAPA tables; UK date stamps in body fields; Why renderer omits empty questions; pack-path ICAM wrap (Inter). Helvetica chronology/ICAM golden fixtures stay byte-identical.
- **Out of scope:** Word `.docx` (R3); C18; Entra; PAMS; size-limit raise; new `en.json` keys; flipping `FF_COMPETENCE_BOARD`.
- **Feature flag / kill switch:** None. Kill SHA = PACK-R1 LIVE `a989c16491d7`.

## 2) Impact Map (what changed)
- **Database:** none.
- **Migration:** none.
- **Backend:** `investigation_pack_pdf.py` (contents/body numbering, UK dates, Why, CAPA table). `investigation_pack_draw.py` (`wrap_text`; pack-path ICAM wrap + row height). Tests.
- **Frontend:** none.
- **APIs:** none (PDF bytes change; routes unchanged).
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Unissued packs live-render with the editorial layout. Packs already issued under C17 keep their retained bytes — a renderer change cannot rewrite a disclosure.
- **Fail closed:** missing Inter or lockup still raises. Helvetica figure goldens still ellipsize; only the Inter pack path wraps ICAM causes.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** No new fields. The pack still reproduces narrative as written (C1). Empty Why questions are omitted, not invented.
- **Lawful basis / retention:** unchanged. Issued PDF retention is still C17.
- **New processor?** No. **Entra?** Untouched, flag stays false.
- **Authorisation:** unchanged (`investigation:update` download / issue).

## 4) Acceptance Criteria (AC)
- [x] AC-01: Contents and body use the same 01–N titles (Incident details, Findings, Root cause analysis, CAPA, Chronology, Evidence schedule, Redaction summary, Pack integrity). The umbrella heading "Report sections" is gone.
- [x] AC-02: Incident metadata is a label/value table; findings are 01. …; CAPA is Reference | Action. ISO dates in those fields render as UK stamps (e.g. 17 May 2026).
- [x] AC-03: Why 1–5 print Answer (and Evidence when present). An empty question is not printed as "Why: Not recorded".
- [x] AC-04: Pack ICAM factor wording wraps in the category block. Chronology/ICAM Helvetica golden fixtures stay byte-identical.
- [x] AC-05: C1 redaction honesty still renders. Chronology remains withheld on external packs. C17 retain-on-issue still stores PDF bytes.

## 5) Testing Evidence
- [x] Unit — `tests/unit/test_investigation_pack_brand.py`, `test_investigation_pack_ir.py`, `test_investigation_pack_pdf.py`, `test_investigation_pack_draw.py`, `test_investigation_pack_issue.py` — 222 passed locally.
- [ ] Full CI — linked after PR checks.

## 6) Critical Journeys
- [x] CUJ-01: Quality lead downloads the PDF for REF-2026-0012 and sees 01 Incident details through Pack integrity matching the contents list, UK dates, and Why answers without a blank "Why: Not recorded" row.
- [x] CUJ-02: After C17 issue, a later download still returns the retained bytes from issue time.

## 7) Observability
- No new metrics. ICAM bands that cannot fit a reserved frame still log `pack_draw_icam_band_clipped`. Render errors surface as 500 on download/issue, same as today.

## 8) Release Plan
- Merge when Ledger + All Checks Passed + Smoke Tests (CRITICAL) are green. C18 stays held. Azure is one SHA.
- After deploy: prod `build_sha` equals this merge SHA; download an unissued pack and confirm numbered sections, UK dates, and wrapped ICAM wording.

## 9) Rollback Plan
- **Owner:** David Harris
- **Rollback trigger:** a customer pack prints "Why: Not recorded" for an empty question, ellipsizes ICAM causes on the Inter pack path, or contents/body numbering disagree.
- **Rollback steps:** Revert the squash; redeploy PACK-R1 `a989c16491d7`. Packs already issued under C17 keep their retained bytes.

## 10) Evidence Pack
- Kill SHA: `a989c16491d7` (INV-PACK-R1 LIVE)
- Head at open: `a989c16491d7`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Editorial layout on the same stored payload; Helvetica goldens unchanged
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
