# Change Ledger (CL-INV-PACK-R5-TOC)

> Adjacent, not fixed here: R6 cover/chrome, R7 body editorial, R8 ICAM bands.
> C18 contraction stays held. Kill SHA is PACK-R4 LIVE `2e032f2585fb`.
> Same stored pack payload — no invented narrative.

## 1) Summary
- **Feature / Change name:** INV-PACK-R5 — contents rows jump to chapter banners
- **User goal:** Click a contents line and land on that section. Same in Word.
- **In scope:** fpdf2 `add_link` / `set_link` from Contents 01–09 to numbered banners; PDF outline; Word bookmark + hyperlink on the same numbers.
- **Out of scope:** Cover tracking, Jet cover band, pagination, finding numerals, ICAM bands, Graphik, C18, retaining Word at issue.
- **Feature flag / kill switch:** None. Kill SHA = PACK-R4 LIVE `2e032f2585fb`.

## 2) Impact Map (what changed)
- **Database:** none.
- **Migration:** none.
- **Backend:** `investigation_pack_layout.bind_section_destination`; `write_contents` stores link ids; Word TOC hyperlinks to `pack-sec-NN`.
- **Frontend:** none.
- **APIs:** none.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Same stored pack payload. Contents order unchanged.
- **Fail closed:** missing Inter / lockup / python-docx still raises.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** No. Navigation only.
- **Lawful basis / retention:** unchanged. Issued artefact remains the PDF checksum from C17.
- **New processor?** No. **Entra?** Untouched, flag stays false.
- **Authorisation:** Word GET still `investigation:update`.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Contents page has internal PDF annotations. Clicking `01 Incident details` lands on that banner.
- [x] AC-02: PDF outline names the numbered chapters.
- [x] AC-03: Word Contents rows are `w:hyperlink` to `pack-sec-NN` bookmarks on the chapter headings.
- [x] AC-04: Contents still starts 01 on the same sheet as the model. No invented contents-only page. No TOC page numbers the model does not have.
- [x] AC-05: Tenant name / Tailwind blue still do not paint the letterhead.

## 5) Testing Evidence
- [x] Unit — `tests/unit/test_investigation_pack_{pdf,docx,brand,ir,issue,draw,content}.py` (259 passed locally) including `TestPackContentsLinks` and `test_contents_rows_hyperlink_to_section_bookmarks`.
- [ ] Full CI — linked after PR checks.

## 6) Critical Journeys
- [x] CUJ-01: Quality lead opens the REF-2026-0012 PDF, clicks Contents `06 CAPA`, and is taken to the CAPA banner.
- [x] CUJ-02: Quality lead opens Download Word and Ctrl/Cmd-clicks Contents `02 Findings` to the bookmark.

## 7) Observability
- No new metrics. Render errors remain 500.

## 8) Release Plan
- Merge when Ledger + All Checks Passed + Smoke Tests (CRITICAL) are green. C18 stays held. Azure is one SHA.
- After deploy: prod `build_sha` equals this merge SHA; re-export REF-2026-0012; click Contents.

## 9) Rollback Plan
- **Owner:** David Harris
- **Rollback trigger:** Contents clicks miss the chapter, or stored narrative invented.
- **Rollback steps:** Revert the squash; redeploy PACK-R4 `2e032f2585fb`. Packs already issued under C17 keep their retained PDF bytes.

## 10) Evidence Pack
- Kill SHA: `2e032f2585fb` (INV-PACK-R4 LIVE)
- Head at open: `2e032f2585fb`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Contents links + outline + Word bookmarks; model still starts 01 on the contents sheet
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
