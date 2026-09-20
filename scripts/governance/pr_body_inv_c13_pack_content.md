# Change Ledger (CL-INV-C13-PACK-CONTENT)

> File-disjoint from C12 (InvestigationDetail, ICAM API, `hsg245ReportSections.ts`,
> `investigationDetailApi.ts`, OpenAPI pair). Do **not** merge this PR until C11 is LIVE
> (it is: prod `build_sha` `c92ec3300485`) **and** C12 is the merge tip after that.
> Named chain C11 → C12 → C13. Azure is one SHA. Structured ICAM rows stay C12/C16;
> this PR does not invent ICAM categories or a fishbone figure.

## 1) Summary
- **Feature / Change name:** INV-C13 — pack renders the investigation (findings, RCA, CAPA)
- **User goal:** Generating a customer pack reprinted the source incident. Findings rows
  (C7 LIVE), 5-Whys/RCA (C10 LIVE) and CAPA (C11 LIVE) never entered pack content under the
  HSG245 ids the UI omits, so an approved omit of `findings` or `root-cause` could remove
  nothing. The pack must render the investigation that was actually written.
- **In scope:** pack assembly + PDF list rendering. Absorbs PR-23 and the pack/generator
  half of PR-24. HSG245 omit ids mapped to real pack keys (`findings`, `root-cause`, `capa`,
  and `event-details` → the source `section_*` keys actually present).
- **Out of scope:** `InvestigationDetail.tsx` and its tests (C12); ICAM / fishbone figure
  (C16); chronology feed wiring (C15 renderer already LIVE — this PR does not query the
  timeline from the PDF module); OpenAPI pair; `src/api/__init__.py`; PAMS; Entra;
  frontend gzip ceiling; dropping leftover `why_1` strings (C18).
- **Feature flag / kill switch:** None. Kill SHA = C11 LIVE `c92ec3300485`.

## 2) Impact Map (what changed)
- **Backend:** new `investigation_pack_content.py` — tenant-scoped load of findings rows,
  RCA (`InvestigationRcaService`), and `capa_actions` for this run; overlay sections keyed
  `findings` / `root-cause` / `capa`; HSG245 omit alias expansion. `generate_customer_pack`
  accepts those overlays; the generate route and `generate_pack_for_investigation` load them.
  PDF renders findings as a numbered list, Whys as Why 1..N, CAPA as title/reference/why_level.
- **Frontend:** none. UI omit ids stay HSG245 (`event-details`, `findings`, …).
- **APIs:** No new public write fields. Generate still returns the stored pack `content`
  object; it now contains investigation sections when those rows exist. No OpenAPI change.
- **Database / flags:** none. Reads only. Lazy findings/RCA conversion on generate is the
  same workspace path (flush in the pack transaction), not a new writer.
- **Workflows/jobs:** none.
- **Tests:** `tests/unit/test_investigation_pack_content.py` (new); omit alias tests; PDF
  list-rendering tests. Existing pack/redaction/chronology tests unchanged in intent.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive overlay. Callers that do not pass overlays still
  copy `data.sections` only (existing unit tests). The HTTP generate path always loads
  overlays. When overlays are supplied, dual-write concatenated keys
  (`section_3_investigation_findings`, `section_4_root_cause`, `rca`) are skipped so the
  pack does not reprint the same words twice.
- **Empty is empty.** Empty findings/CAPA lists and empty Why chains are stated as empty.
  No invented CAPA, finding, Why, ICAM category, or fishbone.
- **Fail closed:** pack source load re-filters on `tenant_id`. A missing or mismatched
  tenant returns empty sources, never another organisation's rows. Generate evidence query
  now also filters `EvidenceAsset.tenant_id` (the service path already did).
- **Chronology:** PDF still does not query the timeline. External and unknown audiences
  still get the C15 withholding. No regression of C14 branding.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** Yes, potentially — findings, Why answers, root-cause and CAPA titles
  are narrative already stored on the investigation. They now appear in the generated pack
  under the same audience redaction pass as other sections. Identity-field redaction is
  unchanged (allow-list of recorded identity fields only). Narrative is still not
  redacted; the C1 honesty notice still says so. Chronology remains internal-only (C15).
- **Lawful basis / retention:** unchanged. No new collection, no new processor, no new
  stored field. Pack content checksum covers the overlay because it is stored on the pack
  entity.
- **Authorisation:** generate still requires `investigation:update` and
  `_assert_investigation_tenant`. Cross-tenant is refused before load.
- **Logs:** none added. No investigation content in logs.
- **QGP never writes PAMS.** No bulk Users, Entra flag stays false.
- **What this PR does not claim:** that structured ICAM rows appear (C12/C16); that a
  chronology is stored in the pack payload (C15 feed still not wired here); that omitting
  `fishbone` removes a figure this PR does not draw.

## 4) Acceptance Criteria (AC)
- [x] AC-01: A pack generated from a run with finding rows, a Why, and a CAPA contains
  those under `findings` / `root-cause` / `capa`, not only `section_1_details`.
- [x] AC-02: Empty findings / Why / CAPA are stated as empty. No invented text.
- [x] AC-03: An approved omit of HSG245 id `findings` withholds the findings section.
  `event-details` withholds the source `section_*` keys actually present for event details
  (`section_1_details`), not the investigation overlay.
- [x] AC-04: PDF renders findings as a list, Whys as Why 1..N, CAPA as
  title/reference/why_level. Chronology/branding from C15/C14 are not regressed.
  External audience does not gain chronology.
- [x] AC-05: Tenant-scoped loads. Mismatch / missing tenant is empty, not a leak.
- [x] AC-06: PDF module does not query the timeline. Evidence schedule still renders
  `included_assets` the generator already built.
- [x] AC-07: No ICAM categories, no fishbone figure. C12 Detail files untouched.
  No OpenAPI pair change. QGP never writes PAMS.
- [x] AC-08: Existing identity redaction on source sections is unchanged.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_pack_content.py`: overlay contains findings +
  Why + CAPA; HSG245 `findings` omit; `event-details` omit maps to `section_1_details`;
  empty lists invent nothing; ICAM/fishbone keys are not copied; load fail-closed on
  tenant mismatch / missing tenant.
- [x] Unit — `tests/unit/test_investigation_wave2_smart_search_omit.py`: existing omit plus
  HSG245 `findings` omit withholds overlay findings.
- [x] Unit — `tests/unit/test_investigation_pack_pdf.py`: list rendering, empty stated,
  omitted findings absent from the PDF, external chronology withholding with findings
  present. Existing chronology tests still pass.
- [x] Unit — `tests/unit/test_investigation_service.py`,
  `test_investigation_approve_close_pack_uat.py`, `test_investigation_pack_draw.py`.
- [x] Integration — `tests/integration/test_investigation_stage2.py` (pack redaction /
  evidence matrix). **160 passed, none skipped** on the suites above.
- [x] Lint/type — `black --check`, `isort --check-only`, `flake8` clean on changed Python;
  `mypy` clean on the new helper and pack PDF; `scripts/check_import_boundaries.py` OK.
- [ ] Full CI — linked after PR checks.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Generate a pack for a run with a finding, Why 1, and a CAPA from that Why —
  pack content includes those sections, not only incident `section_1_details`.
- [x] CUJ-02: Approve omit of `findings` — the findings section is withheld; event details
  remain.
- [x] CUJ-03: Render the PDF — findings numbered, Why 1 labelled, CAPA shows reference
  and why_level. External pack still withholds chronology (no actor name, no running-sheet
  narrative).
- [x] CUJ-04: Generate with empty findings/RCA/CAPA — pack states empty, invents nothing.
- [x] CUJ-05: Another tenant id on load — no findings/RCA/CAPA from that organisation.

## 7) Observability & Ops
- **Logs:** none added.
- **Metrics:** none added.
- **Query cost:** three tenant-scoped reads on generate (findings list, RCA workspace,
  `capa_actions` for this source). PDF still has no query.

## 8) Release Plan
- **Do not merge this PR until C12 is the merge tip** after C11 LIVE (C11 is already LIVE
  `c92ec3300485`). Azure is one SHA. File-disjoint from C12 so this PR may sit open in
  parallel; it is not the merge tip while C12 is next on the named chain.
- **Staging / prod:** no schema change, no flag. After this PR's own deploy, confirm
  `/healthz` and `/api/v1/meta/version` `build_sha` on the merge SHA, then generate a pack
  on a staging investigation that has a finding, a Why and a CAPA and confirm those
  appear in the PDF.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** a pack that invents CAPA/finding/Why text, an omit of `findings`
  that still prints findings, chronology reaching an external pack, or a cross-tenant
  row in pack content.
- **Rollback steps:** Revert the squash on `main` and redeploy previous LIVE SHA
  `c92ec3300485`. No data step — pack rows generated by this code remain; they are
  historical exports. Nothing is migrated.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- No migration
- Kill SHA: `c92ec3300485` (INV-C11 LIVE)
- Head at open: this branch tip (recorded after push)

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (no new public write fields; overlay is stored pack
  content; UI omit ids unchanged)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
