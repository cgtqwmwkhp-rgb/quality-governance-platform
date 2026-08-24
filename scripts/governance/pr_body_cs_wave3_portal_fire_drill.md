# Change Ledger (CL-CS-W3-PR3-PORTAL-FIRE-DRILL)

## 1) Summary
- **Feature / Change name:** Wave 3 PR3 — Portal fire-drill capture (owner-scoped list + complete)
- **User goal (1–2 lines):** An employee who owns an active fire-drill obligation can list it on mobile portal and record completion (notes + pass/fail) without using the staff Compliance Schedule UI.
- **In scope:** Portal service + schemas + routes under `/api/v1/portal/fire-drills`; FE page `/portal/fire-drill`; App route wire; unit tests; authz census debt entries for the two new authenticated-only portal routes
- **Out of scope:** Staff Compliance Schedule UI/client/import/i18n/Incident significant-change; FRA portal capture; evidence/photo upload path (flagged unsupported for v1); org-wide or non-owner complete; DB migrations
- **Feature flag / kill switch:** Existing `COMPLIANCE_SCHEDULE_ENABLED` + `compliance_schedule_kill_switch` (same composition as staff CS routes). Closed → 404.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `PortalFireDrill.tsx`; `portalFireDrillClient.ts`; `App.tsx` route `/portal/fire-drill` under PortalLayout
- **Backend (handlers/services):** `portal_fire_drill_service.py` (allowlist `fire_drill_evacuation`; owner_id == user.id; delegates complete to `ComplianceScheduleService.complete_requirement`)
- **APIs (endpoints changed/added):** `GET /api/v1/portal/fire-drills`; `POST /api/v1/portal/fire-drills/{requirement_id}/complete`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `portal_fire_drill.py` schemas + FE types
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None new (reuses CS opener + kill switch)
- **Dependencies (added/removed/updated):** None
- **Tests:** `tests/unit/test_portal_fire_drill.py`
- **Authz census:** Two owner-scoped portal routes added to `AUTHENTICATED_ONLY_DEBT`; ceiling 465 → 467 (ownership enforced in service; same pattern as portal tool/van)

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive portal endpoints + page; staff CS surface untouched
- **Tolerant reader / strict writer applied?** Yes — FE soft-fails list load; complete only for owned allowlisted rows
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert commit removes routes + page

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Fire-drill occurrence capture from field | Owners must use staff Compliance Schedule UI | Portal `/portal/fire-drill` list + complete for owned `fire_drill_evacuation` rows |
| Template allowlist | N/A | Only `fire_drill_evacuation` (FRA and others 404) |
| Ownership / IDOR | N/A | List and complete require `owner_id == caller`; non-owner / wrong template → 404 (fail closed) |
| Module gate | Staff CS gated | Portal routes use the same CS enable + kill-switch composition |
| Evidence honesty | N/A | `evidence_capture_supported: false` for v1; photo input only when true; evidence_asset_ids rejected until enabled |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `GET /api/v1/portal/fire-drills` returns active requirements with `template_key == fire_drill_evacuation` and `owner_id == caller`, gated by CS enable + kill switch (404 when closed)
- [x] AC-02: `POST /api/v1/portal/fire-drills/{id}/complete` completes via `ComplianceScheduleService.complete_requirement` with notes + check_passed; non-owner / non-allowlisted template → 404
- [x] AC-03: Portal page at `/portal/fire-drill` lists owed drills and completes with notes + check_passed; photo capture UI only when `evidence_capture_supported` is true
- [x] AC-04: Unit tests cover list payload, owner/allowlist rejection, evidence-unsupported validation, and kill-switch 404 helper
- [x] AC-05: Staff Compliance Schedule files listed as forbidden in this change remain untouched

## 5) Testing Evidence (link to runs)
- [x] Lint — `black` / `isort` on touched Python
- [ ] Typecheck — CI
- [ ] Build — CI
- [x] Unit tests — `pytest tests/unit/test_portal_fire_drill.py` (local)
- [ ] Integration tests — CI (additive routes; authz census debt +2)
- [ ] Contract tests (if applicable)
- [ ] E2E Smoke (critical journeys)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Owner with CS open opens `/portal/fire-drill`, sees their active fire-drill obligation(s), and records a passed completion with notes
- [x] CUJ-02: Non-owner or FRA-template requirement cannot be completed via the portal endpoint (404); CS closed → portal fire-drill routes 404

## 7) Observability & Ops
- **Logs:** `portal_fire_drills_list` / `portal_fire_drill_completed` info lines (user_id, totals / ids only)
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Enable CS; assign a `fire_drill_evacuation` requirement with `owner_id` = test portal user; open `/portal/fire-drill`; complete with notes; confirm staff register shows the new record and rolled `next_due_date`. With CS kill switch engaged, confirm portal endpoints 404.
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same portal journey on prod FQDN; confirm `meta/version` `build_sha` matches tip before marking LIVE

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Cross-tenant bleed, non-owner complete, wrong template completable, or portal blanking when CS closed (must 404, not 500)
- **Rollback steps:** Revert squash commit on `main`; redeploy prior image
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready

Made with [Cursor](https://cursor.com)
