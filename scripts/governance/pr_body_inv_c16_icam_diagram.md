# Change Ledger (CL-INV-C16-ICAM-DIAGRAM)

> Adjacent, not fixed here: leftover `contributing_factors` text stays until
> C18. C12 factor CRUD and Detail editor are untouched. C17 issue-gate and
> retain-PDF are untouched. Kill SHA is C13 LIVE `753a343ee101`. Azure stays
> one merge SHA.

## 1) Summary
- **Feature / Change name:** INV-C16 — ICAM contributing-factor diagram in the pack
- **User goal:** C12 stores ICAM four + HSG245 depth. The generated pack still
  only printed leftover contributing-factor *text*. The pack now draws those
  factors as four ICAM bands, using the C15 drawing harness.
- **In scope:** serialise tenant-scoped C12 factors onto the existing
  `root-cause` pack section as `icam_factors`; draw four ICAM bands (cause,
  sub-causes, depth); omit of `root-cause` withholds the figure; draw failure
  falls back to the factors in words; golden fixtures; unit tests.
- **Out of scope:** a second table, a new HSG245 omit id, dropping leftover
  text (C18), C17 issue-gate, Detail/factors API, PAMS, Entra, size-limit
  raise, new en.json keys, OpenAPI (no new endpoint).
- **Feature flag / kill switch:** None. Kill SHA = C13 LIVE `753a343ee101`.

## 2) Impact Map (what changed)
- **Database:** none. Factors already live on `fishbone_diagrams.causes`.
- **Backend:** `serialize_icam_factors` on the RCA overlay; pack PDF renders
  `draw_icam_factors_figure`; `load_investigation_pack_sources` loads the C12
  snapshot tenant-scoped; generate paths pass `factors=`.
- **Frontend:** none.
- **APIs:** none new.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** additive field `icam_factors` on the existing
  `root-cause` section. Leftover contributing-factors paragraph stays. Packs
  generated before this PR have no `icam_factors` key; the renderer draws
  nothing extra rather than claiming "none are recorded".
- **Empty factors:** honest empty copy. No invented categories or text.
- **Unmapped pre-DEC-1 keys:** counted and named, not re-categorised.
- **Omit:** approved `root-cause` omit withholds the whole RCA section,
  including the diagram, because the figure is a field on that section.
- **Fail closed:** factor load uses `InvestigationFactorsService.snapshot`
  (tenant + investigation). A failed/missing tenant load emits no
  `icam_factors` key.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** Factor text may copy workplace narrative already on the
  investigation and already in leftover contributing-factor text. No new
  collection, no new audience, no new export beyond the existing pack.
- **Lawful basis / retention:** unchanged.
- **New processor?** No. **Entra?** Untouched, flag stays false.
- **Authorisation:** existing pack generate (`investigation:update` /
  `_get_investigation_or_404`).
- **Logging:** none new for factor ids.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Pack draws four ICAM categories from stored C12 causes (ids +
  depth). Not a 6M fishbone.
- [x] AC-02: Empty snapshot is honest empty copy; no invented factors.
- [x] AC-03: Approved omit of `root-cause` withholds the figure.
- [x] AC-04: Draw failure falls back to the factors in words.
- [x] AC-05: Leftover contributing_factors text is still emitted.
- [x] AC-06: Unmapped non-ICAM keys are reported, not silently rewritten.
- [x] AC-07: No new table, no OpenAPI, QGP never writes PAMS.

## 5) Testing Evidence (link to runs)
- [x] Unit — `test_investigation_pack_content.py`,
  `test_investigation_pack_draw.py`, `test_investigation_pack_pdf.py`
  (193 passed locally).
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Four ICAM factors with depths appear as four bands in the pack.
- [x] CUJ-02: No factors → "No ICAM contributing factors are recorded".
- [x] CUJ-03: `root-cause` omit → no `icam_factors` in the stored content.
- [x] CUJ-04: Draw exception → factors listed as text with a failure sentence.

## 7) Observability & Ops
- **Logs:** `pack_draw_icam_band_clipped` if a band would overflow (should not
  happen under the cap).
- **Metrics:** none new.

## 8) Release Plan
- Merge when Ledger + All Checks Passed + Smoke Tests (CRITICAL) are green.
  C17 waits. Azure is one SHA.
- After deploy: `build_sha` on prod equals this merge SHA; generate a pack
  for a run with ICAM factors and confirm the four bands render.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** a pack shows another tenant's factors, invents
  factors, or draws an ICAM figure on a pack whose `root-cause` omit was
  approved.
- **Rollback steps:** Revert the squash; redeploy C13 `753a343ee101`. Stored
  `icam_factors` keys on already-generated packs are ignored by older
  renderers.
- **Owner:** David Harris

## 10) Evidence Pack
- Kill SHA: `753a343ee101` (INV-C13 LIVE)
- Head at open: `753a343ee101`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Pack overlay field `icam_factors` on `root-cause`; C15 draw
  harness; no new API
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
