# RR-CUJ gate — Risk Profile lane (2026-07-17)

**Tip SHA:** `2077f30e854ee26a4f7226ab90ff69bf1573eda4` (`origin/main`)  
**Scope:** nine Risk Profile / Register critical user journeys (post RR waves + Admin + PM-PDF + PM-W1b + kill-popup).  
**Product changes in this gate:** none (docs/evidence only).

---

## 1. Automated results

| # | CUJ | Result | Evidence (local tip `2077f30e`) |
|---|-----|--------|----------------------------------|
| 1 | Open register row → `/risk-register/:id` profile (no detail popup) (#1102) | **PASS** | `RiskRegister.test.tsx` — Open / Edit / owner → `/risk-register/88`, `risk-detail-dialog` absent; `App.tsx` route; `RiskHeatMap.test.tsx` `onOpenRisk` |
| 2 | Assess → history + trend + activity | **PASS** | `RiskProfile.test.tsx` assess submit + profile reload; `test_risk_service.py` / `test_risk_register_profile.py` history; `test_risk_notes_activity.py` assess→activity |
| 3 | Add note → notes timeline | **PASS** | `RiskProfile.test.tsx` note post + activity refresh; `test_risk_notes_activity.py` |
| 4 | Create action from profile → CAPA with `returnTo` (#1101) | **PASS** | `RiskProfile.test.tsx` create href `create=1&sourceType=risk&sourceId=42` + encoded `/risk-register/42`; `test_risk_actions_upstream.py` |
| 5 | Upstream links panel (`case_risk_links` / audit refs) | **PASS** | `RiskProfile.test.tsx` upstream deep hrefs; `test_risk_actions_upstream.py` `list_upstream_for_risk` |
| 6 | Calendar `next_review` → profile (#1091) | **PASS** | `test_calendar_feed_service.py` — `href == "/risk-register/7"` |
| 7 | Owner User picker (#1101) | **PASS** | `RiskProfile.test.tsx` picker → `updateOwner` + activity; `test_risk_actions_upstream.py` `update_risk_owner_emits_activity` |
| 8 | Close / status honesty | **PASS** | Profile status badge + 404/error honesty Vitest; list default “excl. closed”; calendar closed → `completed`; triage reject → `closed` (integration + route) |
| 9 | Excel import Register dry-run/commit (#1093); Action Plan→CAPA deferred | **PASS** | `test_risk_register_import_service.py` dry-run/commit; FE `importDryRun` / `importCommit` + `action_plan_skipped` UI copy; service default `action_plan_skipped=True` |

**Suites run (local):**

- Vitest: `RiskProfile.test.tsx`, `RiskRegister.test.tsx`, `riskRegisterClient.test.ts`, `riskRegisterPaths.test.ts`, `RiskHeatMap.test.tsx` → **37 passed**
- Pytest (`.venv` / Python 3.11): `test_risk_register_profile.py`, `test_risk_notes_activity.py`, `test_risk_actions_upstream.py`, `test_risk_service.py`, `test_risk_register_import_service.py`, `test_risk_register_list_slt.py`, `test_risk_heatmap_interactive.py`, `test_calendar_feed_service.py` → **83 passed**

---

## 2. Staging UAT checklist (manual)

Run after staging tip == `2077f30e` (or later tip containing the same RR merges).

| # | Step | Expect | Pass? |
|---|------|--------|-------|
| 1 | Risk Register → click row Open / Edit / owner chip | Navigates to `/risk-register/:id`; **no** detail popup | ☐ |
| 2 | Profile → Assess (change residual) → save | Trend / history / activity update; toast or quiet reload without faux zeros | ☐ |
| 3 | Profile → add note | Note appears in notes timeline; activity shows `note_added` | ☐ |
| 4 | Profile → Create CAPA | Lands on Actions create with `sourceType=risk`, `sourceId`, `returnTo` back to profile | ☐ |
| 5 | Profile → Upstream panel | Incident / audit finding links resolve; empty state if none | ☐ |
| 6 | Calendar → enterprise risk `next_review` event | Click opens `/risk-register/:id` (not legacy popup) | ☐ |
| 7 | Profile → Owner User picker | Select user; owner name updates; activity `owner_changed` | ☐ |
| 8 | Status honesty | Default register excludes closed; closed risk on calendar shows completed; profile badge matches API status; reject triage closes audibly | ☐ |
| 9 | Register → Excel import | Dry-run preview; commit creates/updates Register rows; Action Plan sheet skipped / deferred messaging visible | ☐ |

**Deferred (by design):** Action Plan sheet → CAPA create (post-#1093 / CAPA W3 follow-on).

---

## 3. Gate verdict

**RR-CUJ gate: COMPLETE** via automated evidence on tip `2077f30e`. No product fix PRs required. Staging UAT checklist above is the remaining human sign-off.
