# Change Ledger (CL-INV-C11-CAPA-PER-WHY)

> Adjacent, not fixed here: ICAM / contributing-factor rows are C12. Pack PDF/draw
> (C15 LIVE `e4facada7`) and closure helpers (C8 LIVE) are not in this diff.
> Dual-written `why_1`..`why_5` strings stay until C18. Findings CRUD is
> untouched. C10 merge SHA `796c1115d` is the rollback once C10 is LIVE.
> **Do not merge while C10 #1860 is chasing LIVE** — Azure is one SHA.

## 1) Summary
- **Feature / Change name:** INV-C11 — CAPA per Why (DEC-2)
- **User goal:** After C10 put workspace RCA on `five_whys_analyses`, an
  investigator still could not name which Why a CAPA came from. The register
  (`capa_actions`) had `effectiveness_criteria` but not the review columns the
  RCA-tools `capa_items` row already carried. Absorbs PR-18 (RCA link on
  `capa_actions`) and PR-19 (effectiveness columns + Create-CAPA-from-Why
  control) because the control has to write the same columns the migration
  adds.
- **In scope:** additive `five_whys_id` / `why_level` / effectiveness review
  columns on `capa_actions`; `POST /investigations/{id}/rca/capa`; extend
  existing `POST /investigations/{id}/capa`; RCA tab control per Why; OpenAPI
  pair; unit + smoke + frontend tests.
- **Out of scope:** pack PDF/draw, closure helpers, findings CRUD, ICAM (C12),
  dropping flat-key readers (C18), competence, PAMS, Entra, a second table,
  a second findings editor, size-limit raise.
- **Feature flag / kill switch:** None. Kill SHA = LIVE `e4facada7` (INV-C15).
  Once C10 is LIVE, rollback SHA is C10 squash `796c1115d`.

## 2) Impact Map (what changed)
- **Database:** `capa_actions` gains nullable `five_whys_id` (FK to
  `five_whys_analyses`, ON DELETE SET NULL), `why_level` (1–20 CHECK),
  `effectiveness_review_date`, `is_effective`, `effectiveness_notes`. No
  backfill. No row rewrite.
- **Migration:** `alembic/versions/20261121_inv_c11_capa_per_why.py`,
  revision `20261121_inv_c11_capa_why`, down_revision `20261120_inv_c7_findings`.
  Existence-guarded upgrade; tested downgrade drops only these columns.
- **Backend:** `CAPAService.create_capa_from_why` / Why-link on
  `create_capa_for_investigation`; `POST /investigations/{id}/rca/capa`;
  optional `why_level` / `five_whys_id` on `CreateInvestigationCapaRequest`.
- **Frontend:** InvestigationDetail RCA tab — per-Why "Create CAPA from why N"
  on the lazy chunk as plain English. Empty / unsaved Why disables the control.
  `investigationDetailApi.createCapaFromWhy` (not the shell client).
- **APIs:** `POST /api/v1/investigations/{investigation_id}/rca/capa`. Existing
  `POST /investigations/{id}/capa` accepts the same Why link fields.
  OpenAPI pair updated together and kept byte-identical.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive expand. Existing CAPA rows keep
  `source_type=investigation` / `source_id`. Dual-written leftover `why_1`
  strings are not dropped. Flat-key readers stay until C18. Effectiveness
  review columns are null until a later review writes them.
- **Empty Why:** 422 `Why is empty; CAPA text is not invented`. No 500. The UI
  does not invent a title from a blank slot and the button is disabled until
  that Why is saved with text.
- **Fail closed:** analysis lookup re-filters on `tenant_id` and
  `investigation_id`. Another organisation's row is "no analysis". A
  `five_whys_id` that is not this run's analysis is 404, not a leak.
- **Transactions:** CAPA create still commits in `CAPAService` as before.
  RCA GET/PUT dual-write is unchanged.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** Yes, but no new PII and no new audience. CAPA title/
  description may copy a Why answer that already exists on
  `five_whys_analyses`. The new columns name which Why and record later
  effectiveness review. No new collection, no new export.
- **Lawful basis / retention:** unchanged — legal obligation / legitimate
  interest, existing CAPA / investigation retention. `five_whys_id` is
  ON DELETE SET NULL, so deleting an analysis does not delete the CAPA.
- **New processor?** No. **New egress?** No. **Entra?** Untouched, flag stays
  false.
- **QGP never writes PAMS.** Nothing here touches PAMS, competence, or Users
  bulk.
- **Authorisation:** `POST /rca/capa` declares `investigation:update` and goes
  through `_get_investigation_or_404` (same as C10 RCA). Cross-tenant is
  `TENANT_ACCESS_DENIED` before roles.
- **Logging:** existing `capa.created_from_investigation` audit payload now
  carries `five_whys_id` and `why_level` (ids only). No Why text.

## 4) Acceptance Criteria (AC)
- [x] AC-01: A CAPA can name the Why it came from via `capa_actions.five_whys_id`
  and `why_level`. No second table.
- [x] AC-02: Effectiveness review columns exist on `capa_actions`
  (`effectiveness_review_date`, `is_effective`, `effectiveness_notes`) in
  addition to existing `effectiveness_criteria`.
- [x] AC-03: `POST /api/v1/investigations/{id}/rca/capa` creates a CAPA from a
  Why, tenant-scoped, permission `investigation:update`.
- [x] AC-04: Empty Why is 422 with no invented CAPA text and no 500. Whitespace
  is empty.
- [x] AC-05: Another tenant's analysis with the same `investigation_id` is
  invisible. A mismatched `five_whys_id` is not found.
- [x] AC-06: RCA tab offers Create CAPA from each Why (plain English on the lazy
  chunk). Empty / unsaved Why does not invent text. C10 "Create CAPA from root
  cause" remains.
- [x] AC-07: Dual-write leftover `why_1`..`why_5` readers are not dropped.
  Pack PDF/draw and closure helpers are not in this diff.
- [x] AC-08: Migration is additive with a tested down script. Single alembic
  head. QGP never writes PAMS.
- [x] AC-09: OpenAPI pair records the new path and fields and stays
  byte-identical.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_capa_per_why.py`,
  `tests/unit/test_create_investigation_capa_request_extra_forbid.py`,
  RCA API path mount + permission gate, alembic head pins.
- [x] Smoke — `tests/smoke/test_inv_c11_capa_per_why.py`: empty Why invents
  nothing; filled Why links `five_whys_id` / `why_level`.
- [x] Frontend — vitest on InvestigationDetail + investigationDetailApi:
  per-Why control, empty Why disabled, create posts `/rca/capa`.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Save Why 1, click Create CAPA from why 1 — CAPA lands on
  `capa_actions` with `why_level=1` and this run's `five_whys_id`; title is
  the Why answer, not invented prose.
- [x] CUJ-02: Empty Why 2 — the control is disabled; POST with `why_level=2`
  is 422; no CAPA row.
- [x] CUJ-03: Create CAPA from root cause still opens the existing actions
  form (C10), not a second findings editor.
- [x] CUJ-04: A run with no tenant refuses POST /rca/capa rather than storing
  an unscoped CAPA.
- [x] CUJ-05: Effectiveness review columns are present and null on create;
  they can be set later via CAPA update.

## 7) Observability & Ops
- **Logs:** existing capa-created-from-investigation audit; Why ids only.
- **Metrics:** existing `investigations.create_capa`.
- **Query cost:** one extra tenant-scoped `five_whys_analyses` SELECT when
  `why_level` / `five_whys_id` is set.

## 8) Release Plan
- **Do not merge this PR until C10 #1860 squash `796c1115d` is LIVE**
  (`build_sha` matches). Azure is one SHA. Kill SHA while C15 is LIVE is
  `e4facada7`.
- **Staging / prod:** additive schema, no flag. After this PR's own deploy,
  confirm `/healthz` and `/api/v1/meta/version` `build_sha` on the merge SHA,
  then on a staging investigation with a saved Why create a CAPA from Why 1
  and confirm the row names that Why.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** a CAPA attributed to the wrong tenant's Why, invented
  CAPA text from an empty Why, or a 500 on an empty Why.
- **Rollback steps:** Revert the squash on `main` and redeploy previous LIVE
  SHA. Today that is C15 `e4facada7`. Once C10 is LIVE, rollback is C10
  `796c1115d`. The new columns remain until down-script; they are nullable
  so older code ignores them. No data-drop of existing CAPAs.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- Migration: `20261121_inv_c11_capa_why`
- Kill SHA: `e4facada7` (INV-C15 LIVE)
- C10 merge SHA (rollback once C10 is LIVE): `796c1115d`
- Head at open: `796c1115d` (INV-C10 squash, not yet LIVE)

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (`POST /investigations/{id}/rca/capa`;
  OpenAPI pair updated; `capa_actions` additive columns)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
