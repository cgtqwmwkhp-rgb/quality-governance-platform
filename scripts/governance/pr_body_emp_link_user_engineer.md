# Change Ledger (CL-EMP-LINK-USER-ENGINEER)

## File allowlist (exclusive)
- `src/domain/models/engineer.py`
- `src/domain/services/engineer_user_link_service.py`
- `src/domain/services/pams_technician_sync_service.py`
- `src/api/schemas/engineer.py`
- `src/api/routes/engineers.py`
- `src/api/routes/users.py`
- `alembic/versions/20260725_engineer_qgp_profile_override.py`
- `tests/unit/test_engineer_identity_controls.py`
- `tests/unit/test_engineer_user_link_and_override.py`
- `frontend/src/api/workforceClient.ts`
- `frontend/src/pages/workforce/EngineerProfile.tsx`
- `scripts/governance/pr_body_emp_link_user_engineer.md`

**Out of scope:** Employees roster list/compact UI (EMP-UI PR); incident/complaint picker swap (same EMP-UI PR); PAMS write-back (never).

## 1) Summary
- **Feature / Change name:** EMP-LINK — User↔Engineer link + QGP-only profile edit
- **User goal:** Every new QGP user gets a person (Engineer) record; admins can link/unlink and edit profiles on QGP without touching PAMS; PAMS re-sync cannot clobber QGP edits.
- **In scope:** link/unlink APIs; auto Engineer on User create; `qgp_profile_override`; profile edit UI; sync preserve.
- **Out of scope:** Roster view modes; governance assignee picker rollout.
- **Feature flag / kill switch:** None — revert commit + downgrade migration.

## 2) Impact Map (what changed)
- **Frontend:** EngineerProfile edit + UserEmailSearch link/unlink; workforceClient PATCH/link APIs.
- **Backend:** `POST .../link-user`, `POST .../unlink-user`; User create → `ensure_engineer_for_user_async`; PATCH sets override; list/get include `linked_user`.
- **APIs:** Additive engineer link endpoints + response fields.
- **Schemas/contracts:** `EngineerUpdate.display_name`, `qgp_profile_override`, `LinkedUserSummary`.
- **Database:** `engineers.qgp_profile_override` boolean (default false).
- **Workflows/jobs/queues:** PAMS sync skips identity overwrite when override=true.
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None — PATCH still rejects `user_id` mutation (message points to link-user).
- **Migration plan:** Alembic add column with server_default false.
- **Rollback strategy (DB):** Downgrade drops column; revert commit.

## 4) Acceptance Criteria (AC)
- [x] AC-01: link-user / unlink-user attach/detach User without PAMS write
- [x] AC-02: User create with tenant_id auto-creates or links Engineer
- [x] AC-03: PATCH identity fields set `qgp_profile_override=true`
- [x] AC-04: PAMS sync preserves identity when override=true; still updates is_active + PAMS ids
- [x] AC-05: EngineerProfile can edit profile and link/unlink via UI

## 5) Testing Evidence (link to runs)
- [x] Unit: `test_engineer_user_link_and_override.py` + identity controls (13 passed locally)
- [ ] CI — this PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin links PAMS roster person to QGP login on profile
- [x] CUJ-02: Admin edits display name on QGP; re-sync does not overwrite
- [x] CUJ-03: Creating a tenant user ensures an Engineer person record

## 7) Observability & Ops
- **Logs:** `engineer_user_linked`, `engineer_user_unlinked`, `engineer_qgp_profile_updated`, auto-link/create logs
- **Metrics / Alerts:** N/A
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Create user → Employees shows linked; edit name → Sync from PAMS → name retained; unlink/link.
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same + migration applied.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Link failures / sync incorrectly skipping updates
- **Rollback steps:** Revert squash-merge; alembic downgrade `20260725_eng_qgp_ov`; force_deploy prior SHA
- **Owner:** Tip-owner

## 10) Evidence Pack (links)
- CI: after PR open
- Canvas: `qgp-employees-pams-profiles-360`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts — Person ≠ Login; PAMS write = never
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary — N/A
- [ ] **Gate 5:** Production verification plan ready
