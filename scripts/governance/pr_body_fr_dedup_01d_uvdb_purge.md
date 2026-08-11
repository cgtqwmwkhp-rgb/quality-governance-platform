# Change Ledger (CL-FR-DEDUP-01D-UVDB-PURGE)

> Base: `origin/main` @ tip LIVE `fd9f0f07` (#1718). Serial after #1719.
> Stops UVDB Audit Status twins surviving a register purge.

## 1) Summary

- **Feature / Change name:** FR-DEDUP-01d — purge `uvdb_audit` with duplicate audit runs
- **User goal (1–2 lines):** Purging a twin `AUD-…` must also remove its UVDB Audit Status catalogue row so `/uvdb` stops showing the twin.
- **Problem:** `uvdb_audit` has no FK to `audit_runs` — only `audit_reference` string equality. FR-DEDUP-01 FK closure never saw those rows; PROD purge of `AUD-2026-0043` left the twin on UVDB Audit Status.
- **In scope:**
  - `scripts/ops/run027/_uvdb_catalogue.py` plan/apply by `audit_reference`
  - Wire into `purge_duplicate_audit_runs` plan, apply, manifest, trail
  - Unit fixture + assertions for catalogue + children
- **Out of scope:** Import idempotency (#1719); OCR draft clustering (FR-DEDUP-03); Planet Mark twins (FR-DEDUP-04).
- **Feature flag / kill switch:** N/A — ops script path.

## 2) Impact Map

- **Backend / ops:** `scripts/ops/run027/_uvdb_catalogue.py` (new), `purge_duplicate_audit_runs.py`
- **Tests:** `tests/unit/test_run027_duplicate_audit_purge.py`
- **APIs / DB / flags:** No migration. Explicit DELETE by planned ids.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive catalogue purge inside the same transaction.
- **Breaking changes:** None for API. Dry-run JSON gains `uvdb_catalogue`; apply payload gains `uvdb_catalogue_rows`.
- **Migration plan:** N/A. Historical orphans purged by re-running the ops script.
- **Rollback strategy:** Revert merge; redeploy prior tip. Already-deleted rows stay deleted (ops irreversible by design).

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Twin on `/uvdb` after register purge | Survives (no FK) | Deleted with run by `audit_reference` |
| Children `uvdb_audit_response` / `uvdb_kpi_record` | Orphan or cascade-only | Explicit children-first delete |
| Audit trail | Register only | Includes `uvdb_audit` snapshots |

## 4) Acceptance Criteria (AC)

- [x] **AC-01:** Dry-run reports matching `uvdb_audit` (+ children) for purged references.
- [x] **AC-02:** Apply deletes those catalogue rows in the same transaction as the register purge.
- [x] **AC-03:** Survivor `uvdb_audit` (different reference) is untouched.
- [x] **AC-04:** Residual `uvdb_audit` for purged refs aborts commit.
- [x] **AC-05:** Change Ledger + Gate Checklist present.

## 5) Testing Evidence

- [x] `pytest tests/unit/test_run027_duplicate_audit_purge.py` — local after wire-up
- [ ] Full CI after PR open

## 6) Critical Journeys (CUJ)

- [x] **CUJ-01:** Dry-run twin refs → `uvdb_catalogue.row_count == 2`.
- [x] **CUJ-02:** Apply → twin catalogue gone; survivor catalogue remains.

## 7) Observability & Ops

- Trail metadata requirement: `FR-DEDUP-01 / FR-DEDUP-01d`
- Manifest includes `uvdb_catalogue` block

## 8) Release Plan

- Allowlist after #1719 LIVE → admin-merge → tip-chase → optional ops re-purge if orphans remain

## 9) Rollback Plan

- **Trigger:** Legitimate UVDB row sharing a purged reference wrongly deleted (should not happen — refs unique).
- **Steps:** Revert squash; restore from manifest / backup if needed.
- **Owner:** Platform / conveyor

## 10) Evidence Pack

- Local unit: after wire-up
- CI / tip LIVE: after merge

---

# Gate Checklist

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — dry-run/apply JSON additive only
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A)
- [x] **Gate 5:** Rollback = revert
- [~] **UX Coverage Gate:** HOLD — ignored per conveyor instruction
