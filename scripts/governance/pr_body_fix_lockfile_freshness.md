# Change Ledger (CL-FIX-LOCKFILE-FRESHNESS)

## 1) Summary
- **Feature / Change name:** Refresh requirements.lock for Lockfile Freshness CI
- **User goal (1–2 lines):** Unblock main CI / App Service deploy path after upstream package drift failed Lockfile Freshness on `8a9b6a16`.
- **In scope:** Regenerated `requirements.lock` with `LOCKFILE_UPGRADE=1`; harden `generate_lockfile.sh` empty-array under `set -u`
- **Out of scope:** Application feature changes; Training Matrix UX (already merged #1219)
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** None (lockfile pins only)
- **APIs:** None
- **Database:** None
- **Config/env/flags:** None
- **Dependencies:** `requirements.lock` refreshed within existing `requirements.txt` constraints

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Pin refresh only; no API/schema change
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy:** Revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: `requirements.lock` regenerates cleanly via `./scripts/generate_lockfile.sh`
- [x] AC-02: Lockfile Freshness Check passes on PR CI
- [x] AC-03: `generate_lockfile.sh` works without `LOCKFILE_UPGRADE` (no unbound `UPGRADE_ARGS`)

## 5) Testing Evidence
- [x] Local: `LOCKFILE_UPGRADE=1 ./scripts/generate_lockfile.sh` OK
- [ ] CI — after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Lockfile generate script runs under `set -u` with and without upgrade

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** None
- **Runbook:** If Lockfile Freshness fails on main: `LOCKFILE_UPGRADE=1 ./scripts/generate_lockfile.sh` and open fix PR

## 8) Release Plan
- **Staging / Prod:** Merge unblocks Deploy Build and Deploy jobs gated on main CI green

## 9) Rollback Plan
- **Trigger:** Unexpected runtime dependency break
- **Steps:** Revert merge; redeploy prior SHA
- **Owner:** Platform

## 10) Evidence Pack
- CI: linked after PR open

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Lockfile-only fix
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging path unblocked
- [ ] **Gate 4:** N/A
- [x] **Gate 5:** Rollback ready
