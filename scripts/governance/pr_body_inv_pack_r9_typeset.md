# Change Ledger (CL-INV-PACK-R9-TYPESET)

> Adjacent, not fixed here: Word after issue (C17 still retains PDF only).
> C18 contraction stays held. Kill SHA is PACK-R8 LIVE `1257b31f7500`.
> Same stored pack payload — no invented narrative.

## 1) Summary
- **Feature / Change name:** INV-PACK-R9 — in-house spacing, narrative panels, reverse lockup, kit palette
- **User goal:** The customer PDF matches the in-house report on spacing, text boxes, chapter titles, line rhythm, and the five kit colours including the white lockup on the Jet band.
- **In scope:** Official palette hex; reverse lockup + plantexpand.com on the cover band; confidentiality / description / RCA panels; contents and finding air; numbered banners `01 INCIDENT DETAILS`; Immediate actions catalogue title. Word numbered headings match.
- **Out of scope:** Graphik, rewriting stored sentences, inventing ICAM factors, Lime/Dodger as page chrome, retaining Word at issue, C18.
- **Feature flag / kill switch:** None. Kill SHA = PACK-R8 LIVE `1257b31f7500`.

## 2) Impact Map (what changed)
- **Database:** none.
- **Migration:** none.
- **Backend:** `investigation_pack_brand` palette + reverse lockup; cover band; layout leading/panels/banners; catalogue title; Word numbered headings.
- **Frontend:** none.
- **APIs:** none.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Same stored pack payload. Empty ICAM still prints the honest line.
- **Fail closed:** missing Inter / lockup / reverse lockup / python-docx / fpdf2 still raises.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** No. Typesetting only.
- **Lawful basis / retention:** unchanged. Issued artefact remains the PDF checksum from C17.
- **New processor?** No. **Entra?** Untouched, flag stays false.
- **Authorisation:** Word GET still `investigation:update`. Working copy still closes after issue.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Palette constants are Jet #333030, Crimson #BA3737, Lime #BEDA41, Dodger #2868CE, Platinum #EBE8E8. Tenant Tailwind blue still does not paint the letterhead.
- [x] AC-02: Cover Jet band embeds the reverse lockup and `plantexpand.com`. Cover stays unnumbered. Missing reverse lockup fails closed.
- [x] AC-03: Description / recording notes / immediate harm / RCA problem and root cause sit in panels. Confidentiality on the cover is a Platinum panel with a Lime alert bar. Empty root cause stays a sentence, not a box.
- [x] AC-04: Contents rows are 9 mm. Numbered banners paint `01 INCIDENT DETAILS`. Contents list stays 1–n sentence case. `section_2_immediate_actions` catalogues as Immediate actions.
- [x] AC-05: Stored finding / Why / CAPA wording is unchanged. No Graphik. Word working copy still exists before issue and still closes after issue.

## 5) Testing Evidence
- [x] Unit — `tests/unit/test_investigation_pack_{pdf,docx,brand,ir,issue,draw,content}.py` — 263 passed locally.
- [ ] Full CI — linked after PR checks.

## 6) Critical Journeys
- [x] CUJ-01: Quality lead exports REF-2026-0013: cover band shows the white lockup and website; 02 is Immediate actions; description is boxed; findings 01–03 still wrap in full.
- [x] CUJ-02: Download Word before issue still works. Numbered chapters match the PDF caps. Issued packs still refuse the working copy.

## 7) Observability
- No new metrics. Render errors remain 500.

## 8) Release Plan
- Merge when Ledger + All Checks Passed + Smoke Tests (CRITICAL) are green. C18 stays held. Azure is one SHA.
- After deploy: prod `build_sha` equals this merge SHA; re-export REF-2026-0013.

## 9) Rollback Plan
- **Owner:** David Harris
- **Rollback trigger:** Cover grows a second page, stored narrative invented, or reverse lockup missing and the pack still renders Helvetica.
- **Rollback steps:** Revert the squash; redeploy PACK-R8 `1257b31f7500`. Packs already issued under C17 keep their retained PDF bytes.

## 10) Evidence Pack
- Kill SHA: `1257b31f7500` (INV-PACK-R8 LIVE)
- Head at open: `1257b31f7500`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Palette, reverse lockup, panels, contents air, chapter titles; Word after issue not in this PR
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
