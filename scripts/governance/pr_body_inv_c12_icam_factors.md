# Change Ledger (CL-INV-C12-ICAM-FACTORS)

> Adjacent, not fixed here: pack rendering of structured ICAM is C16 (diagram)
> and C13 (pack content already open as #1862, file-disjoint). Flat
> `contributing_factors` readers stay until C18. Findings CRUD, CAPA-per-Why,
> pack PDF/draw, and omit UI ids are untouched. Kill SHA is C11 LIVE
> `c92ec3300485`. Azure stays one merge SHA. Do not merge C13 (#1862) first.

## 1) Summary
- **Feature / Change name:** INV-C12 — ICAM contributing factors (DEC-1)
- **User goal:** Contributing factors were one free-text box. DEC-1 is ICAM
  four categories crossed with HSG245 causal depth. An investigator can pick a
  category, list factors beneath it, and the API round-trips those fields.
- **In scope:** re-specify unused `FishboneCategory` 6M → ICAM four; HSG245
  `CausalDepth`; store factors on existing `fishbone_diagrams.causes` JSON
  (id, cause, sub_causes, depth); `GET/POST/PATCH/DELETE /investigations/{id}/factors`;
  RCA-tab picker+list; dual-write leftover contributing_factors string/list;
  OpenAPI pair; unit + frontend tests.
- **Out of scope:** pack PDF/draw (C13/C15/C16), a second table, dropping
  leftover readers (C18), PAMS, Entra, size-limit raise, new en.json keys.
- **Feature flag / kill switch:** None. Kill SHA = C11 LIVE `c92ec3300485`.

## 2) Impact Map (what changed)
- **Database:** none. `fishbone_diagrams.causes` is already JSON. Depth is a
  key on each cause object. No alembic revision.
- **Backend:** `FishboneCategory` ICAM values; `CausalDepth`;
  `investigation_factors_service.py`; `investigation_factors.py` router;
  dual-write via existing RCA workspace sync; RCA PUT does not clobber
  factors when contributing_factors is omitted.
- **Frontend:** `InvestigationFactorsEditor` on the lazy Detail chunk as
  plain English. Replaces the contributing-factors textarea.
- **APIs:** `/api/v1/investigations/{investigation_id}/factors`. OpenAPI pair
  updated together and kept byte-identical.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** unused 6M enum replaced. Stored JSON keyed by
  old 6M names is counted as `unmapped_categories`, not re-categorised and
  not dropped. Dual-write keeps leftover string/list readers in step.
- **Empty factor text:** 422, not invented. Depth required on create.
- **Fail closed:** every query re-filters `tenant_id`. Missing tenant refuses
  writes. Cross-tenant is not-found / TENANT_ACCESS_DENIED.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** Factor text may copy workplace narrative already on the
  investigation. No new collection, no new audience, no new export.
- **Lawful basis / retention:** unchanged.
- **New processor?** No. **Entra?** Untouched, flag stays false.
- **Authorisation:** `investigation:update` plus `_get_investigation_or_404`.
- **Logging:** `investigation_factor_created` with ids only.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Factors are stored under ICAM four on `fishbone_diagrams`, not a
  second table.
- [x] AC-02: Each factor has category, cause, optional sub-causes, HSG245
  depth. Empty cause is 422.
- [x] AC-03: List/create/update/delete tenant-scoped under `/factors`.
- [x] AC-04: Leftover `contributing_factors` string (flat and nested) and
  five_whys list stay in step; readers not dropped.
- [x] AC-05: RCA tab picker+list in plain English. No new en.json keys.
- [x] AC-06: Pre-DEC-1 6M keys are reported, not silently rewritten.
- [x] AC-07: OpenAPI pair identical. QGP never writes PAMS.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_factors_api.py` and fishbone
  extra-forbid / phase2 fishbone tests.
- [x] Frontend — vitest InvestigationDetail + icamFactors.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Add a factor under organisational / immediate — listed with
  those names; leftover string rewritten.
- [x] CUJ-02: Blank cause refused; no invented text.
- [x] CUJ-03: Another tenant's diagram is invisible.
- [x] CUJ-04: Delete last factor leaves a valid empty list.

## 7) Observability & Ops
- **Logs:** investigation_factor_created (ids).
- **Metrics:** none new.

## 8) Release Plan
- Merge when Ledger + All Checks Passed + Smoke Tests (CRITICAL) are green.
  C13 #1862 stays held until this is LIVE. Azure is one SHA.
- After deploy: `build_sha` on prod equals this merge SHA; on staging add
  one ICAM factor and confirm GET round-trips it.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** a factor attributed to the wrong tenant, invented
  factor text, or leftover readers showing a stale paragraph after a
  mutation.
- **Rollback steps:** Revert the squash; redeploy C11 `c92ec3300485`. JSON
  depth keys remain harmless to older code.
- **Owner:** David Harris

## 10) Evidence Pack
- Kill SHA: `c92ec3300485` (INV-C11 LIVE)
- Head at open: `c92ec3300485`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (`/investigations/{id}/factors`;
  OpenAPI pair; ICAM enum)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
