# Change Ledger (CL-FR-ASSIST-CORE-01)

> Base: `origin/main` @ `d0bf093b` (#1723).
> Security fix: Assist register reads were ungated; now permission-declared.

## 1) Summary

- **Feature / Change name:** FR-ASSIST-CORE-01 — Assist tool registry + RBAC spine
- **User goal:** Assist answers only from tools the caller may invoke under the same `*:read` tokens as the registers.
- **Problem:** Assist queried incidents/NM/complaints/actions without `incident:read` etc.; only Compliance was gated. Closed-intent #1724 superseded.
- **In scope:** `src/domain/services/assist/` registry; `tool_is_visible` before gather; vehicle gatherers harvested; `_resolve_assist_tool_tokens` in `DECLARED_DYNAMIC_SITES`; contract + unit tests.
- **Out of scope:** Planner; find_records default; FE welcome copy; new register depth tools beyond vehicle harvest.
- **Feature flag:** Unchanged (`AI_COPILOT_*`).

## 2) Impact Map

- **Backend:** `assist/{types,permissions,registry,tools/vehicles}.py`; `copilot_grounding.py` RBAC gate; `authz/extraction.py` resolver
- **Tests:** `test_assist_registry.py`; updated grounding / inference tests
- **Frontend / DB / APIs:** None

## 3) Compatibility & Data Safety

- **Breaking (intentional):** Callers lacking `incident:read` (etc.) no longer receive those Assist figures — security fix.
- **Rollback:** Revert merge; redeploy. No schema.

## Compliance Delta

| Control | Before | After |
| --- | --- | --- |
| Assist incident/NM/complaint/action reads | Auth-only | `*:read` via ASSIST_TOOLS |
| Assist vehicle defect reads | N/A / ungated intent PR closed | Auth-only with recorded reason |
| Permission catalogue | No Assist site | DECLARED_DYNAMIC_SITES + resolver |

## 4) Acceptance Criteria

- [x] AC-01: ASSIST_TOOLS names == GROUNDED_INTENTS; every required_permission ∈ ENFORCED_PERMISSIONS or auth_only_reason set
- [x] AC-02: try_answer without entitlement → UNGROUNDED (no figures)
- [x] AC-03: Compliance kill-switch still short-circuits before user/register lookup
- [x] AC-04: Vehicle top-failures / open-defect intents gather with tenant filter
- [x] AC-05: Permission catalogue scan includes Assist dynamic site
- [x] AC-06: No test skipped/loosened

## 5) Testing Evidence

- [x] `python3.11 -m pytest tests/unit/test_assist_registry.py tests/unit/test_copilot_grounded_inference.py tests/unit/test_copilot_grounded_compliance.py tests/unit/test_permission_catalogue.py -q` — **95 passed**
- [ ] Full CI / tip LIVE — after merge

## 6) Critical Journeys

- [x] CUJ-01: Admin (superuser) asks incident count → answered
- [x] CUJ-02: User without incident:read asks incident count → ungrounded refuse path
- [x] CUJ-03: Module-off compliance → ungrounded, zero SQL

## 7–10) Ops / Release / Rollback / Evidence

Serial tip-chase STG→PROD with `release_sha`. Rollback = revert deploy. Evidence = unit suite above.

---

# Gate Checklist

- [x] Gate 0–3
- [ ] Gate 4 CI green
- [ ] Gate 5 tip LIVE
