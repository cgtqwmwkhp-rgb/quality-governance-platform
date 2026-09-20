# Change Ledger (CL-INV-PACK-R4-WRAP)

> Adjacent, not fixed here: C18 leftover-reader contraction stays held. Kill SHA is
> PACK-R3 LIVE `ec30f72f8214`. Azure stays one merge SHA. Same stored pack payload —
> no invented narrative. Word remains a working copy, not a second issued artefact.

## 1) Summary
- **Feature / Change name:** INV-PACK-R4 — wrap inside frames and restore the template chapters
- **User goal:** The exported investigation PDF keeps every stored sentence inside its box, separates sections the way the Plantexpand template does, and still offers Word to amend before issue.
- **In scope:** wrapping tables (no `cell()[:80]`); description / findings / Why / root-cause / integrity panels; 01–09 chapters when ICAM is stored; Word tables wrap the same titles; Report tab label “Download Word”.
- **Out of scope:** C18; Entra; PAMS; Graphik; retaining Word at issue; pixel-identical replica of the designed PDF; Helvetica chronology/ICAM goldens.
- **Feature flag / kill switch:** None. Kill SHA = PACK-R3 LIVE `ec30f72f8214`.

## 2) Impact Map (what changed)
- **Database:** none.
- **Migration:** none.
- **Backend:** `investigation_pack_layout.py`; PDF writer tables wrap; RCA splits contributing-factor table and ICAM into their own chapters when `icam_factors` is stored; Word working copy follows.
- **Frontend:** Report tab Word button label only (`Download Word`). Still disabled after issue.
- **APIs:** none.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Same stored pack payload. Packs without `icam_factors` keep the C13 contributing prose and do not grow an ICAM chapter.
- **Fail closed:** missing Inter / lockup / python-docx still raises.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** No new fields. The renderer prints the stored titles in full instead of cutting them at 80 characters.
- **Lawful basis / retention:** unchanged. Issued artefact remains the PDF checksum from C17.
- **New processor?** No. **Entra?** Untouched, flag stays false.
- **Authorisation:** Word GET still `investigation:update`. PDF download stays on the authenticated-only debt list.

## 4) Acceptance Criteria (AC)
- [x] AC-01: A CAPA action title longer than one column prints in full in the PDF and the Word working copy. No `[:80]` clip.
- [x] AC-02: Findings, description, root cause and pack integrity sit in framed blocks. A long finding continues on the next page rather than vanishing at the box edge.
- [x] AC-03: When `icam_factors` is stored, contents and body use the template chapters 04 Contributing factors and 05 ICAM contributing factors. Empty ICAM still says none were recorded.
- [x] AC-04: Report tab still downloads Word for an unissued pack; after issue the button stays closed (C17).
- [x] AC-05: Tenant name / Tailwind blue still do not paint the letterhead. Helvetica chronology/ICAM goldens untouched.

## 5) Testing Evidence
- [x] Unit — `tests/unit/test_investigation_pack_{pdf,docx,brand,ir,issue,draw,content}.py` (256 passed locally). Long CAPA title and long finding assertions added.
- [ ] Full CI — linked after PR checks.

## 6) Critical Journeys
- [x] CUJ-01: Quality lead generates the REF-2026-0012 internal pack. CAPA-2026-0010 ends with “Forestry England sites”, not “Forestry Engla”.
- [x] CUJ-02: Quality lead clicks Download Word on an unissued pack, edits locally, then issues; the customer artefact is still the retained PDF.

## 7) Observability
- No new metrics. Render errors remain 500. Issued-pack Word remains 409 `PACK_WORKING_COPY_CLOSED`.

## 8) Release Plan
- Merge when Ledger + All Checks Passed + Smoke Tests (CRITICAL) are green. C18 stays held. Azure is one SHA.
- After deploy: prod `build_sha` equals this merge SHA; re-export REF-2026-0012; confirm CAPA titles wrap; confirm Download Word on an unissued pack.

## 9) Rollback Plan
- **Owner:** David Harris
- **Rollback trigger:** CAPA titles still clipped, stored narrative invented, or Word served after issue.
- **Rollback steps:** Revert the squash; redeploy PACK-R3 `ec30f72f8214`. Packs already issued under C17 keep their retained PDF bytes.

## 10) Evidence Pack
- Kill SHA: `ec30f72f8214` (INV-PACK-R3 LIVE)
- Head at open: `ec30f72f8214`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Wrap inside frames; template 01–09 when ICAM is stored; Word still a working copy
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
