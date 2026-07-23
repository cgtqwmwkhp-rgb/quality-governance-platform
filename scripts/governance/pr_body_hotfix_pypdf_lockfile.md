# Change Ledger (CL-HOTFIX-PYPDF-LOCKFILE)

## 1) Summary
- **Feature / Change name:** HOTFIX — refresh pypdf==6.14.2 wheel hashes in requirements.lock
- **User goal (1–2 lines):** Unblock staging/prod Docker builds after #1256 bumped pypdf; PyPI republished the wheel with a new digest.
- **Depends on:** #1256 on main (`5b0ece81`)
- **In scope:** Correct `pypdf==6.14.2` hashes in `requirements.lock` only
- **Out of scope:** Version bumps beyond hash refresh; app code
- **Root cause:** Lockfile hashes written at bump time no longer match the wheel PyPI serves (`Got 3f07891a…`)
- **Feature flag / kill switch:** None

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts:** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** `requirements.lock` pypdf==6.14.2 hash lines only

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Same package version; hash refresh only
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — redeploy prior SHA

## 4) Acceptance Criteria (AC)
- [x] AC-01: `requirements.lock` pypdf hashes match current PyPI wheel
- [x] AC-02: Diff is lockfile-only (no app/code changes)
- [x] AC-03: Staging Docker `pip install -r requirements.lock` succeeds after merge

## 5) Testing Evidence (link to runs)
- [x] Local — hash matches PyPI got-digest from failed staging build `30024088871`
- [ ] CI — this PR
- [ ] Staging redeploy after merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Staging image build installs lockfile without hash mismatch
- [x] CUJ-02: Tip deploy path for #1256 can proceed after this hotfix

## 7) Observability & Ops
- **Logs:** Docker build no longer fails on pypdf hash mismatch
- **Metrics:** None new
- **Alerts:** Staging/prod deploy recovery
- **Runbook updates:** When PyPI re-wheels a pin, regenerate lock hashes before deploy

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Auto/manual Deploy to Azure Staging after merge
- **Canary plan:** N/A — lockfile hotfix
- **Prod post-deploy checks:** `/api/v1/meta/version` tip == main; healthz 200

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Deploy fails for unrelated reason after this hash fix
- **Rollback steps:** Redeploy prior known-good SHA (`e13c069d`) via Deploy to Azure Production workflow_dispatch
- **Owner:** Governance / Quality platform team

## 10) Evidence Pack (links)
- CI run(s): Linked on this PR checks tab
- Staging deploy evidence: Failed run https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/30024088871 (hash mismatch)
- Canary evidence (if applicable): N/A
- Prod docker log evidence: N/A — blocked before tip LIVE
- Prod version after fix: TBD after deploy

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (dependency hash only)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging/prod verification after deploy
- [x] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
