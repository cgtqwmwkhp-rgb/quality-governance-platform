# Change Ledger — SYS-06 Investigation FE/BE CUJ (closure probe)

## Summary

- **Change:** Stop `GET /investigations/{id}/closure-validation` from returning HTTP 500 on draft / from-incident investigations; harden template validation; FE probe honesty (no faux success, no toast spam).
- **User outcome:** Incident → create investigation → detail shows a real closure checklist (`can_close=false` when not ready) or an inline retry — CAPA handoff CTA remains.
- **Scope:** investigation closure validation service + route, InvestigationDetail probe UX, null-safe list/search helpers on the CUJ path, unit tests, this ledger.

## Impact Map

| Area | Disposition | Impact |
|---|---|---|
| `validate_closure` | Fixed | Uses `parse_structure_json` + nested `data.sections`; skips malformed nodes instead of AttributeError. |
| Closure route | Fixed | Fail-soft around open-work + template validation; returns 200 readiness payload when investigation exists. |
| Axios toast | Fixed | `suppressErrorToast` for closure probe — inline honesty UI only. |
| Null-safety | Fixed | UserEmailSearch / Incidents / Investigations / `getStatusDisplay` tolerate missing name/title/reference/status. |

## Compatibility

- No migrations or response-schema removals.
- Drafts continue to return `can_close=false` with `STATUS_NOT_COMPLETE` (and other readiness reasons).
- Existing CAPA open-work gate unchanged when queries succeed.
- CAPA handoff deep-link (`/actions?sourceType=investigation&sourceId=…`) unchanged.

## Acceptance Criteria

- [x] AC-01: Malformed `template.structure.sections` (dict / None entries) does not raise in `validate_closure`.
- [x] AC-02: From-record wrapped `data.sections` is read for required-field checks.
- [x] AC-03: Route fail-soft — unexpected open-work/template errors become reason codes, not HTTP 500.
- [x] AC-04: FE closure probe uses `suppressErrorToast`; unavailable state has Retry (no faux zero / faux ready).
- [x] AC-05: CAPA handoff CTA from InvestigationDetail still navigates to Actions filtered by investigation source.
- [ ] AC-06: Tip LIVE — create-from-incident CUJ shows checklist without Server error toasts.

## Testing Evidence

- [ ] `pytest tests/unit/test_investigation_closure_validate.py -q`
- [ ] `npx vitest run src/api/investigationsClient.test.ts src/pages/__tests__/InvestigationDetail.test.tsx`
- [ ] Required CI green after push.

## Critical Journeys

- [x] CUJ-01: Incident → Create investigation → detail loads; closure probe does not toast 500.
- [x] CUJ-02: Draft investigation closure checklist shows not-ready reasons (not “Unable to load” from 500).
- [x] CUJ-03: CAPA handoff from investigation detail still opens Actions with investigation source filter.
- [ ] CUJ-04: Tip LIVE verify on prod SWA + API tip.

## Observability

- Structured logs: `closure_validation_open_work_failed`, `closure_validation_template_failed`.
- Monitor 5xx rate on `/api/v1/investigations/*/closure-validation` → expect drop to ~0.

## Release Plan

1. Open PR; wait required CI green.
2. Squash-merge after review (authoring step does **not** merge).
3. Deploy tip; create investigation from an incident; confirm checklist 200 + no Server error toasts; CAPA handoff works.

## Rollback Plan

- **Owner:** On-call application engineer / release manager.
- **Rollback steps:** revert squash-merge commit and redeploy.
- **Decision trigger:** closure probe regressions or incorrect `can_close=true`.

## Evidence Pack

- Unit: `tests/unit/test_investigation_closure_validate.py`
- FE: InvestigationDetail unavailable/retry + CAPA handoff tests
- Prod meta version after deploy
- Screenshot/network of closure-validation 200 on a draft from-incident investigation

---

# Gate Checklist

- [x] **Gate 0:** scope, Change Ledger, acceptance criteria, rollback reviewed.
- [ ] **Gate 1:** lint / type surfaces green.
- [ ] **Gate 2:** focused unit suites green.
- [ ] **Gate 3:** deployed CUJ verified.
- [x] **Gate 4:** canary not required; readiness-probe hardening.
- [ ] **Gate 5:** tip LIVE evidence attached.

## Allowlist (hard paths)

- `src/api/routes/investigations.py`
- `src/domain/services/investigation_service.py`
- `frontend/src/api/investigationsClient.ts` (+ test)
- `frontend/src/pages/InvestigationDetail.tsx` (+ test)
- `frontend/src/pages/Investigations.tsx` / `Incidents.tsx` (null-safe search only)
- `frontend/src/components/UserEmailSearch.tsx`
- `frontend/src/utils/investigationStatusFilter.ts`
- `frontend/src/i18n/locales/en.json` / `cy.json` (soft-union keys)
- `tests/unit/test_investigation_closure_validate.py`
- `scripts/governance/pr_body_investigation_closure_validation_500.md`

**Out of scope:** RiskHeatMap / RiskProfile, PlanetMark, Admin, App.tsx, Alembic.
