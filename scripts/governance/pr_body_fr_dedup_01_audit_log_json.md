# Change Ledger (CL-FR-DEDUP-01-AUDIT-LOG-JSON)

> Base: `origin/main` @ tip LIVE `a5ce9f30` (#1716 Assist depth).
> Ops-only fix for PROD apply of FR-DEDUP-01 keep-0048 purge.

## 1) Summary

- **Feature / Change name:** FR-DEDUP-01 apply fix — JSON-safe audit-log payloads
- **User goal (1–2 lines):** Governed purge apply must record the hash-chained trail entry without rolling back when row snapshots contain `datetime` values.
- **Problem:** PROD `--apply` failed at `audit_log_entries` flush: `TypeError: Object of type datetime is not JSON serializable`. Deletes rolled back; `AUD-2026-0043` remains.
- **In scope:**
  - `scripts/ops/run027/_chain.py` — `_json_safe()` round-trip via `json.dumps(..., default=str)` for `old_values` / `new_values` / `entry_metadata` before ORM insert
  - Unit test proving datetime payloads become JSON-safe
- **Out of scope:** Purge plan changes, schema, API, frontend.
- **Feature flag / kill switch:** N/A (ops script only).

## 2) Impact Map

- **Ops:** `scripts/ops/run027/_chain.py`
- **Tests:** `tests/unit/test_run027_duplicate_audit_purge.py`
- **Backend / APIs / Database / Config / Dependencies:** None.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive serialization only; hash path already used `default=str`.
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy:** Revert merge; redeploy prior tip. No schema/data migration.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Purge trail on apply | Fails when snapshots include datetime | Serializes then writes trail in same txn |
| Hash chain integrity | `compute_hash` already `default=str` | Same values fed to ORM JSON binder |
| Accidental apply without trail | Deletes rolled back on failure | Unchanged — trail still required in txn |

## 4) Acceptance Criteria (AC)

- [x] **AC-01:** `_json_safe` converts datetime-bearing nested dicts to JSON-serializable structures.
- [x] **AC-02:** Unit test covers AC-01.
- [x] **AC-03:** Change Ledger present for PR gates.
- [x] **AC-04:** PROD keep-0048 apply succeeded (2026-08-11): `AUD-2026-0043` gone; CAPA 18 → source_id 832; trail seq 165.

## 5) Testing Evidence

- [x] Unit — `pytest tests/unit/test_run027_duplicate_audit_purge.py::test_json_safe_round_trips_datetimes_for_the_audit_log_binder` — **passed** locally
- [ ] Full CI — after PR open

## 6) Critical Journeys (CUJ)

- [x] **CUJ-01:** Operator runs flagged `--apply` for purge `AUD-2026-0043` keep `AUD-2026-0048`; trail entry writes; txn commits.
- [x] **CUJ-02:** On datetime-bearing row snapshots, apply no longer raises `TypeError` at `audit_log_entries` flush.

## 7) Observability & Ops

- **Logs / metrics / alerts:** Existing purge JSON / manifest unchanged
- **Runbook:** `docs/ops/duplicate-audit-purge-runbook.md` — apply still requires dry-run review + `--i-understand-prod`.

## 8) Release Plan

- Conveyor admin-merge when green → tip-chase STG/PROD → then re-run PROD apply (keep 0048 / purge 0043) if not already applied via laptop ops with this patch.

## 9) Rollback Plan

- **Trigger:** Apply or trail hash verification breaks.
- **Steps:** Revert squash on `main`; redeploy prior tip via standard CD. No DB downgrade.
- **Owner:** Platform / conveyor

## 10) Evidence Pack

- Local: `test_json_safe_round_trips_datetimes_for_the_audit_log_binder` passed
- CI / staging / prod tip: linked after merge and LIVE verify
- Ops: PROD apply keep-0048 / purge-0043 verified separately (0043 gone, CAPA 18 remapped, trail present)

---

# Gate Checklist

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — ops script only; no API/schema change
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A — ops script)
- [x] **Gate 5:** Rollback = revert; no flags
- [~] **UX Coverage Gate:** HOLD — ignored per conveyor instruction
