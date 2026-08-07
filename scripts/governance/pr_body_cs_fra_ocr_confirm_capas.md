# Change Ledger (CL-CS-FRA-OCR-CONFIRM-CAPAS)

## 1) Summary
- **Feature / Change name:** FRA OCR confirm → CAPAs for checked rows (pipeline slice 5)
- **User goal (1–2 lines):** When an operator confirms an FRA OCR draft, create CAPA actions only for the priority-action rows they checked — never from OCR alone and never when the flag is off.
- **In scope:** `CAPAAutoService.create_from_fra_ocr_actions`; confirm path gated by `COMPLIANCE_SCHEDULE_FRA_OCR_ACTIONS_ENABLED` (default OFF); `CAPASource.FRA_OCR` + alembic ADD VALUE; deploy vars + env-vars.json persistence; unit tests
- **Out of scope:** Slice 6 Risk; Doc Graph; changing FRA OCR ingest flag default; FE redesign; Azure appsettings full PUT
- **Feature flag / kill switch:** `COMPLIANCE_SCHEDULE_FRA_OCR_ACTIONS_ENABLED` / `compliance_schedule_fra_ocr_actions_enabled` — **default OFF**. Persist across deploys via `vars.*` (same pattern as FRA OCR / filing index).

## 2) Impact Map (what changed)
- **Frontend:** None (confirm already sends checked rows)
- **Backend:** `capa_auto_service.py`, `compliance_schedule_fra_ocr_service.py`, `capa.py` enum
- **APIs:** `actions_created` on confirm applied summary may be >0 when flag on; no new endpoints
- **Database:** Alembic `20261017_capa_fra_ocr` — `ALTER TYPE capasource ADD VALUE IF NOT EXISTS 'fra_ocr'`
- **Config/env/flags:** config + deploy-staging/production + `scripts/infra/env-vars.json`
- **Dependencies:** None
- **Tests:** empty-actions confirm test unchanged; flag-off/on confirm tests; `test_capa_from_fra_ocr.py`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive enum label + flag-gated behaviour; default preserves today’s `actions_created=0`
- **Tolerant reader / strict writer applied?** Confirm body unchanged (`extra=forbid`)
- **Breaking changes:** None
- **Migration plan:** Expand-only enum ADD VALUE (irreversible label; safe unused until flag on)
- **Rollback strategy (DB):** Leave enum label; set flag false / revert app code

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| CAPA from FRA OCR priority actions | Recorded on draft only (`actions_created=0`) | Flag on: CAPAs for checked rows only |
| Empty / unchecked actions | No CAPAs | Still no CAPAs (empty-actions test retained) |
| Silent CAPA creation | Impossible | Still impossible without confirm + flag + checked rows |
| Flag persistence across deploy | N/A | Deploy vars + env-vars registry |

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** With flag OFF, confirm with checked actions records them and leaves `actions_created=0` (no CAPAAutoService call).
- [x] **AC-02:** With flag ON, confirm with N checked rows creates N CAPAs (`source_type=fra_ocr`, idempotent per draft+index).
- [x] **AC-03:** With flag ON and `actions=[]`, `actions_created=0` and CAPAAutoService is not called.
- [x] **AC-04:** Existing `test_apply_confirmed_plan_updates_next_due_date_only` remains unchanged and green.
- [x] **AC-05:** Migration adds `fra_ocr` via `ADD VALUE IF NOT EXISTS`; enum parity test covered by provisioning string.
- [x] **AC-06:** Deploy workflows + env-vars registry persist `COMPLIANCE_SCHEDULE_FRA_OCR_ACTIONS_ENABLED` (default false if unset).

## 5) Testing Evidence
- [x] Unit — confirm flag gates + `test_capa_from_fra_ocr.py`
- [ ] Full CI — after PR open

## 6) Critical Journeys (CUJ)
- [x] **CUJ-01:** Flag off → Confirm FRA draft with checked rows → due date applied; Actions list unchanged.
- [x] **CUJ-02:** Flag on → Confirm with two checked rows → two OPEN CAPAs linked to `fra_ocr_draft:{id}`.
- [x] **CUJ-03:** Flag on → Confirm with no rows checked → no CAPAs.

## 7) Observability & Ops
- **Logs:** confirm log includes `actions_created`; audit payload includes `capa_reference_numbers`
- **Runbook:** `gh variable set COMPLIANCE_SCHEDULE_FRA_OCR_ACTIONS_ENABLED --body true|false` and/or merge-only `az webapp config appsettings set` (never full PUT)

## 8) Release Plan
- Squash-merge to `main` → Main CI → Azure staging then prod → verify tip SHA + health.
- Bake: leave flag **false** until operator opts in.

## 9) Rollback Plan
- **Trigger:** Unexpected CAPA volume or wrong source linkage
- **Rollback owner:** Platform / on-call (sole operator: David Harris)
- **Steps:**
  1. `gh variable set COMPLIANCE_SCHEDULE_FRA_OCR_ACTIONS_ENABLED --body false`
  2. Merge-only `az webapp config appsettings set ... COMPLIANCE_SCHEDULE_FRA_OCR_ACTIONS_ENABLED=false` (never full PUT)
  3. Revert squash on main if code fix required; redeploy prior tip

## 10) Evidence Pack
- CI / staging / prod tip: linked after merge and LIVE verify

---

# Gate Checklist
- [x] Gate 0 — Scope lock + AC + Change Ledger (slice 5 only)
- [x] Gate 1 — Contracts (flag default off; additive enum; confirm body unchanged)
- [ ] Gate 2 — CI green
- [ ] Gate 3 — Staging verification
- [ ] Gate 4 — Canary (N/A — flag off)
- [x] Gate 5 — Rollback via var/appsetting documented
