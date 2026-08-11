# Change Ledger (CL-FR-DEDUP-02-IMPORT-IDEMPOTENCY)

> Base: `origin/main` @ tip LIVE `fd9f0f07` (#1718).
> Stops Achilles / Planet Mark twin re-create on external intake.

## 1) Summary

- **Feature / Change name:** FR-DEDUP-02 — external audit import identity gate
- **User goal (1–2 lines):** Re-importing the same Achilles / Planet Mark report must not mint another `AUD-…` twin; operator is sent to the existing run.
- **Problem:** Job idempotency keys only on `(run_id, asset, checksum)`. Each intake created a new run → new UVDB catalogue row. PROD accumulated dozens of Achilles shells; `/audits/26/import-review` is one leftover pending twin of completed `AUD-2026-0048`.
- **In scope:**
  - `create_run` 409 when tenant + non-empty `external_reference` already exists
  - Require `external_reference` for `achilles_uvdb` / `planet_mark`
  - UVDB sync fallback: update by `company_id` instead of minting a second catalogue row
  - FE: surface 409 and deep-link to existing import-review
- **Out of scope:** Purge script `uvdb_audit` coverage (FR-DEDUP-01d); OCR draft clustering; deleting historical twins (ops).
- **Feature flag / kill switch:** N/A — API refuse path.

## 2) Impact Map

- **Backend:** `src/api/routes/audits.py`, `src/api/schemas/audit.py`, `src/domain/services/external_audit_idempotency.py` (new), `external_audit_promotion_service.py`
- **Frontend:** `frontend/src/pages/Audits.tsx`
- **Tests:** unit idempotency + schema; integration duplicate 409
- **APIs / DB / flags:** No migration. Behavioural 409 + stricter validation.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive refuse. Blank `external_reference` still allowed for `customer` / `iso` / `other`.
- **Breaking changes:** Achilles / Planet Mark create without `external_reference` → 422.
- **Migration plan:** N/A. Historical twins remain until ops purge.
- **Rollback strategy:** Revert merge; redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Twin Achilles intake | New run every time | 409 + existing run id/ref |
| UVDB catalogue | New row per run ref | Reuse by company_id when present |
| Operator UX | Silent twin | Message + navigate to survivor |

## 4) Acceptance Criteria (AC)

- [x] **AC-01:** Second external intake with same tenant + `external_reference` returns 409 and creates no run.
- [x] **AC-02:** 409 details include `existing_run_id` + `existing_reference_number`.
- [x] **AC-03:** `achilles_uvdb` / `planet_mark` require non-empty `external_reference`.
- [x] **AC-04:** Distinct `external_reference` still creates a new run.
- [x] **AC-05:** UVDB sync updates existing `company_id` row rather than always inserting.
- [x] **AC-06:** Change Ledger + Gate Checklist present.

## 5) Testing Evidence

- [x] `pytest tests/unit/test_external_audit_idempotency.py` — 7 passed
- [x] `pytest tests/unit/test_audit_schemas.py::TestAuditRunCreate` — passed
- [ ] Full CI after PR open
- [ ] Integration duplicate 409 (included; run in CI)

## 6) Critical Journeys (CUJ)

- [x] **CUJ-01:** Import Achilles with `00019685` twice → second 409 → UI opens existing run.
- [x] **CUJ-02:** Import with a different supplier id → new run created.

## 7) Observability & Ops

- Endpoint metric reason: `external_reference_duplicate`
- Ops: leftover pending twins (`AUD-2026-0017`, `AUD-2026-0026`) are historical shells — purge separately; do not promote.

## 8) Release Plan

- Allowlist → conveyor admin-merge → tip-chase STG/PROD → verify 409 on duplicate create.

## 9) Rollback Plan

- **Trigger:** Legitimate second audits with shared supplier ids falsely 409.
- **Steps:** Revert squash; redeploy prior tip. Narrow match key in follow-up if needed.
- **Owner:** Platform / conveyor

## 10) Evidence Pack

- Local unit: idempotency 7/7; schema create tests green
- CI / tip LIVE: after merge

---

# Gate Checklist

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — 409 detail additive; Achilles/PM require external_reference
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A)
- [x] **Gate 5:** Rollback = revert
- [~] **UX Coverage Gate:** HOLD — ignored per conveyor instruction
