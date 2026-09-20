# Change Ledger (CL-INV-PACK-R3-WORD)

> Adjacent, not fixed here: C18 leftover-reader contraction stays held. Kill SHA is
> PACK-R2 LIVE `dd5a05c3db30`. Azure stays one merge SHA. Same stored pack payload —
> no invented narrative. Word is a working copy, not a second issued artefact.

## 1) Summary
- **Feature / Change name:** INV-PACK-R3 — Word working copy from the same investigation pack IR
- **User goal:** A quality lead can download an editable `.docx` of an unissued pack, amend wording, and still issue the retained PDF (C17 DEC-5).
- **In scope:** python-docx renderer from the stored pack payload; `GET …/packs/{id}/docx` gated on `investigation:update`; Report-tab Word button; 409 `PACK_WORKING_COPY_CLOSED` after issue.
- **Out of scope:** C18; Entra; PAMS; size-limit raise; new `en.json` keys; flipping `FF_COMPETENCE_BOARD`; retaining Word at issue; drawing the ICAM vector in Word.
- **Feature flag / kill switch:** None. Kill SHA = PACK-R2 LIVE `dd5a05c3db30`.

## 2) Impact Map (what changed)
- **Database:** none. No `issued_docx_*` columns.
- **Migration:** none.
- **Backend:** `investigation_pack_docx.py`; `GET /investigations/{id}/packs/{pack_id}/docx`; issue tests.
- **Frontend:** Report tab Word button on the lazy Detail chunk (`investigationDetailApi`, helpers). Disabled after issue.
- **APIs:** additive GET. Not added to `AUTHENTICATED_ONLY_DEBT`.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Unissued packs live-render Word from the stored payload. Issued packs keep C17 retained PDF bytes; Word returns 409 and does not re-render.
- **Fail closed:** missing python-docx or lockup raises; the route returns 500 rather than an empty file.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** No new fields. Word reproduces the same stored pack narrative as the PDF (C1).
- **Lawful basis / retention:** unchanged. Issued artefact remains the PDF checksum from C17. Word is not retained.
- **New processor?** No. **Entra?** Untouched, flag stays false.
- **Authorisation:** `investigation:update` on the Word GET. PDF download stays on the authenticated-only debt list.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Unissued pack Word download is OOXML (`PK`), same catalogue titles and UK date stamps as the PDF, Why 1–5 omit empty questions.
- [x] AC-02: After C17 issue, Word GET raises 409 `PACK_WORKING_COPY_CLOSED`. Issue still retains PDF only (`issued_pdf_*`).
- [x] AC-03: Report tab Word button downloads the working copy; after issue the button is disabled and copy says the working copy is closed.
- [x] AC-04: Tenant `organisation_name` / `primary_color` do not paint the letterhead. ICAM in Word is a text list of stored factors plus a note that the diagram is in the PDF.
- [x] AC-05: Missing python-docx or lockup fails closed. Chronology remains withheld on external packs.

## 5) Testing Evidence
- [x] Unit — `tests/unit/test_investigation_pack_{brand,ir,pdf,draw,issue,docx}.py` (232 passed locally) plus InvestigationDetail / helper Word UI tests (51 passed).
- [ ] Full CI — linked after PR checks.

## 6) Critical Journeys
- [x] CUJ-01: Quality lead downloads Word for an unissued pack, edits locally, then issues; the customer artefact is still the retained PDF.
- [x] CUJ-02: After issue, Word is closed (409 / disabled button). PDF download returns the retained bytes.

## 7) Observability
- No new metrics. Render errors surface as 500 on the Word GET. Issued-pack Word attempts are 409 with `PACK_WORKING_COPY_CLOSED`.

## 8) Release Plan
- Merge when Ledger + All Checks Passed + Smoke Tests (CRITICAL) are green. C18 stays held. Azure is one SHA.
- After deploy: prod `build_sha` equals this merge SHA; download Word on an unissued pack; confirm issued packs refuse Word.

## 9) Rollback Plan
- **Owner:** David Harris
- **Rollback trigger:** Word is served after issue, Word is retained as a second artefact, or lockup/python-docx missing is papered over with an empty file.
- **Rollback steps:** Revert the squash; redeploy PACK-R2 `dd5a05c3db30`. Packs already issued under C17 keep their retained PDF bytes.

## 10) Evidence Pack
- Kill SHA: `dd5a05c3db30` (INV-PACK-R2 LIVE)
- Head at open: `dd5a05c3db30`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Word from the same IR; issued artefact stays PDF
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
