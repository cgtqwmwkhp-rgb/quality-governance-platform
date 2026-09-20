# Change Ledger (CL-INV-PACK-R6-CHROME)

> Adjacent, not fixed here: R7 body editorial, R8 ICAM bands.
> C18 contraction stays held. Kill SHA is PACK-R5 LIVE `589b41382be2`.
> Same stored pack payload — no invented narrative.

## 1) Summary
- **Feature / Change name:** INV-PACK-R6 — cover band, tracking, unnumbered cover, two-rail footer
- **User goal:** The pack chrome matches the model: Jet cover band, tracked labels, PAGE n from the first body page, INVESTIGATION REPORT header, — CONTENTS 1–9.
- **In scope:** Cover Jet band + tracked caps; running header INVESTIGATION REPORT; two-rail footer; cover outside PAGE n of m; Contents as — CONTENTS with 1–9 (links from R5 kept). Word first-page vs body chrome.
- **Out of scope:** Findings numerals, Why table, CAPA air, integrity mono, ICAM bands, Graphik, Lime/Dodger chrome, C18, retaining Word at issue.
- **Feature flag / kill switch:** None. Kill SHA = PACK-R5 LIVE `589b41382be2`.

## 2) Impact Map (what changed)
- **Database:** none.
- **Migration:** none.
- **Backend:** `investigation_pack_brand.write_tracked`; pack FPDF `{nb}` is body pages; cover/header/footer/contents chrome; Word different-first-page header/footer.
- **Frontend:** none.
- **APIs:** none.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Same stored pack payload. Chapter numbers on banners stay 01–09.
- **Fail closed:** missing Inter / lockup / python-docx / fpdf2 still raises.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** No. Chrome only.
- **Lawful basis / retention:** unchanged. Issued artefact remains the PDF checksum from C17.
- **New processor?** No. **Entra?** Untouched, flag stays false.
- **Authorisation:** Word GET still `investigation:update`.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Cover has no PAGE n. Body footers read PAGE 1 OF m where m is PDF pages minus the cover.
- [x] AC-02: Cover foot is a Jet Grey band with the Wickford address. Running footer legal line is not on the cover.
- [x] AC-03: Body header is INVESTIGATION REPORT · reference. Footer is two-rail: REF · UNCONTROLLED WHEN PRINTED | AUDIENCE · PAGE n OF m.
- [x] AC-04: Contents is — CONTENTS with items 1–9. Numbered banners and R5 links/outline still work. 01 still starts on that sheet.
- [x] AC-05: No Lime, Dodger, or Graphik in the pack. Tenant name / Tailwind blue still do not paint the letterhead.

## 5) Testing Evidence
- [x] Unit — `tests/unit/test_investigation_pack_{pdf,docx,brand,ir,issue,draw,content}.py` (259 passed locally) including unnumbered cover and PAGE 1 OF body-count.
- [ ] Full CI — linked after PR checks.

## 6) Critical Journeys
- [x] CUJ-01: Quality lead opens REF-2026-0012 PDF: cover has no page number; contents is PAGE 1; clicking 6 still lands on CAPA.
- [x] CUJ-02: Download Word shows INVESTIGATION REPORT on body pages and — CONTENTS with 1–9 hyperlinks.

## 7) Observability
- No new metrics. Render errors remain 500.

## 8) Release Plan
- Merge when Ledger + All Checks Passed + Smoke Tests (CRITICAL) are green. C18 stays held. Azure is one SHA.
- After deploy: prod `build_sha` equals this merge SHA; re-export REF-2026-0012 and check cover/chrome.

## 9) Rollback Plan
- **Owner:** David Harris
- **Rollback trigger:** Cover numbered again, PAGE total counts the cover, or stored narrative invented.
- **Rollback steps:** Revert the squash; redeploy PACK-R5 `589b41382be2`. Packs already issued under C17 keep their retained PDF bytes.

## 10) Evidence Pack
- Kill SHA: `589b41382be2` (INV-PACK-R5 LIVE)
- Head at open: `589b41382be2`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Unnumbered cover, Jet band, tracked chrome, PAGE n from body, — CONTENTS 1–9; R5 links kept
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
