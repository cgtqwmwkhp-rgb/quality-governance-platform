# Change Ledger (CL-AM-NOTIFY)

## 1) Summary
- **Feature / Change name:** AM-NOTIFY — Safety asset 30/60/90 (+ overdue) expiry notifications
- **User goal (1–2 lines):** Daily Celery sweep notifies asset owners and a configurable admin role when SAFETY-category assets enter exclusive expiry bands, with deep links to `/safety-assets/:id` and per-(user, asset, band) dedupe.
- **In scope:** `safety_asset_expiry_tasks.py`, Celery include + beat registration, unit tests for band selection/dedupe, this ledger.
- **Out of scope:** FE pages/Layout, workforce, VehicleChecklists, incident models, SMTP/email delivery (in-app only).
- **Feature flag / kill switch:** Admin role via `SAFETY_ASSET_EXPIRY_ADMIN_ROLE` (default `admin`). Disable by removing beat entry / not running worker.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None (deep-link path reserved for AM-FE).
- **Backend (handlers/services):** New Celery task module only; uses existing `Notification` model.
- **APIs (endpoints changed/added):** None.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None.
- **Database (migrations/entities/indexes):** None (writes into existing `notifications` table).
- **Workflows/jobs/queues (if any):** Beat `check-safety-asset-expiry` daily 07:30 UTC → queue `notifications`.
- **Config/env/flags:** `SAFETY_ASSET_EXPIRY_ADMIN_ROLE` (optional, default `admin`).
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive task + beat schedule. Uses existing `CERTIFICATE_EXPIRING` / `CERTIFICATE_EXPIRED` notification types; category key `safety_asset_expiry` in `extra_data` for prefs/consumers.
- **Tolerant reader / strict writer applied?** Yes — missing owner/admin simply skips recipients; assets outside bands ignored.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy (DB):** Revert PR; existing notifications remain harmless history.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Sweep SAFETY assets with `expiry_date` and/or `next_service_due`; classify exclusive bands overdue / due_30 / due_60 / due_90.
- [x] AC-02: Notify owner + users with configurable admin role; in-app channel recorded.
- [x] AC-03: `action_url` is `/safety-assets/:id`.
- [x] AC-04: Deduplicate per (user, asset, band) so repeat beat runs do not re-notify.
- [x] AC-05: Unit tests cover band selection + dedupe (+ Celery registration/beat).

## 5) Testing Evidence (link to runs)
- [x] Unit tests — `pytest tests/unit/test_safety_asset_expiry_tasks.py`
- [ ] Lint / Typecheck / Build — CI
- [ ] Integration / E2E — N/A (task helpers; no API surface)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Asset due in 20 days → `due_30` band → owner + admin notified with `/safety-assets/{id}`
- [x] CUJ-02: Second sweep same band → skipped via dedupe
- [x] CUJ-03: Asset crosses into `due_30` from `due_60` → new band notification allowed

## 7) Observability & Ops
- **Logs:** Task completion summary (`assets_scanned`, `in_band`, `notifications_created`, `notifications_skipped_dedupe`)
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Depends on:** #976 (AM-MODEL) for asset owner/expiry spine
- **Staging verification:** Confirm beat registered; optionally run task once against staging DB with a seeded SAFETY asset
- **Prod post-deploy checks:** Celery worker imports task; beat entry present; sample notification after first daily run

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Notification spam or task errors impacting worker health
- **Rollback steps:** Revert PR (removes beat + module); drain/ignore queued task name if any
- **Owner:** Platform / Safety Assets track

## 10) Evidence Pack (links)
- CI run(s): Linked on PR checks
- Staging deploy evidence: After merge + staging deploy

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Contracts additive (notifications only)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan + monitoring ready

## Exclusive allowlist
- `src/infrastructure/tasks/safety_asset_expiry_tasks.py` (new)
- `src/infrastructure/tasks/celery_app.py` (include + beat)
- `tests/unit/test_safety_asset_expiry_tasks.py` (new)
- `scripts/governance/pr_body_am_notify.md`
