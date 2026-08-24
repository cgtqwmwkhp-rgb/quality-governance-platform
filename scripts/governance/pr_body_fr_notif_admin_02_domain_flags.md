# Change Ledger (CL-FR-NOTIF-ADMIN-02-DOMAIN-FLAGS)

## 1) Summary
- **Feature / Change name:** FR-NOTIF-ADMIN-02 first slice — per-domain notification FeatureFlag toggles (Incident, default-OFF)
- **User goal (1–2 lines):** Admins can enable Incident case-owner assignment notify from Notification Settings; missing/unseeded rows stay **off** (unlike Compliance Schedule, which stays default-on).
- **In scope:** `incident_owner_assignment_notify` helper (seed `enabled=False`); Feature Flags GET/PATCH/list seed; gate on Incident owner-assign producer; inventory honesty + Admin UI toggle + en/cy i18n; unit tests.
- **Out of scope:** Flipping CS polarity; gating all ~20 producers; fake channel cards; Layout.tsx; alembic; CRITICAL/SOS paths.
- **Feature flag / kill switch:** New flag `incident_owner_assignment_notify` (default-off / missing → no send). CS notify flags unchanged.

## 2) Impact Map (what changed)
- **Frontend:** `NotificationSettings.tsx` — Incident notify toggle section (superuser PATCH); i18n en/cy keys for CS + Incident sections.
- **Backend:** `incident_notify_flags.py` (seed/evaluate default-off); gate in `incidents._notify_case_owner_assignment`; Feature Flags list/get/patch seed incident keys; inventory producer `feature_flags` + absent-row polarity for default-off keys.
- **APIs:** Existing `/api/v1/feature-flags/` seed paths extended (no new endpoints). Inventory GET still does **not** seed flags.
- **Schemas/contracts:** None.
- **Database:** None (no alembic) — flag rows inserted on Feature Flags read/write only.
- **Workflows/jobs/queues:** None.
- **Config/env/flags:** One `feature_flags` row key `incident_owner_assignment_notify`.
- **Dependencies:** None.
- **Tests:** Default-off evaluate; gate bite on/off; inventory honesty; GET seed; FE toggle row present.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive flag + gate. Prior behaviour for Incident owner notify is preserved when the flag is **enabled**; fresh DBs stay silent until an admin turns it on (intentional behaviour change vs previous always-send).
- **Tolerant reader / strict writer applied?** Yes — missing row = off at evaluate and in inventory reporting.
- **Breaking changes:** Environments that relied on unflagged Incident owner assignment notify will stop sending until the admin enables the flag (documented; default-off is the FR requirement).
- **Migration plan:** N/A — no alembic.
- **Rollback strategy (DB):** No schema change — set flag `enabled=true` to restore prior send behaviour, or revert deploy.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Incident owner assignment notify | Always attempted on owner change | Gated by `incident_owner_assignment_notify` (missing/disabled → no send) |
| Admin control of Incident notify | None | Superuser toggle on Notification Settings + Feature Flags API |
| CS notify polarity | Default-on | Unchanged |
| Inventory honesty for producer flags | CS absent = on only | CS absent = on; Incident absent = off |
| Inventory GET seeding | Does not seed | Still does not seed |
| CRITICAL / SOS producers | Untouched | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `incident_owner_assignment_notify` seeds with `enabled=False`; evaluate missing row as False; Feature Flags GET/PATCH for the key seeds without migration.
- [x] AC-02: Incident owner-assignment producer does not call `NotificationService.create_assignment` when the flag is off/missing; when on, prior create_assignment behaviour is preserved.
- [x] AC-03: Inventory declares `feature_flags=("incident_owner_assignment_notify",)` for `incident_owner_assigned` and reports absent row as enabled=false / persisted=false; Inventory GET creates no flag rows.
- [x] AC-04: Admin Notification Settings shows an Incident toggle that PATCHes the flag (superuser); en/cy strings present.
- [x] AC-05: No CS polarity change; no alembic; Layout.tsx untouched; CRITICAL/SOS untouched.

## 5) Testing Evidence
- [x] `python3.11 -m pytest tests/unit/test_incident_notify_flags.py tests/unit/test_notification_inventory.py tests/unit/test_notification_inventory_route.py tests/unit/test_compliance_schedule_assignment_notify.py -q` — **78 passed**
- [x] `cd frontend && npx vitest run src/pages/admin/__tests__/NotificationSettings.test.tsx` — **13 passed**
- [ ] Full CI on PR

## 6) Critical Journeys
- [x] CUJ-01: Fresh DB / missing flag → assign Incident case owner → no assignment notification; inventory shows flag off (default).
- [x] CUJ-02: Superuser enables `incident_owner_assignment_notify` on Notification Settings → assign/reassign owner → in-app assignment notify fires as before.

## 7) Observability & Ops
- Existing incident assignment failure log path unchanged when send is attempted.
- Flag-off path is silent (early return) — intentional.
- Seed logs: `Seeded Incident notify flag … (enabled=False)`.

## 8) Release Plan
1. Merge after CI green.
2. Main CI → Azure deploy → verify ACA tip SHA + health.
3. Confirm flag present via Admin → Notification Settings or `GET /api/v1/feature-flags/incident_owner_assignment_notify` (seeded disabled).
4. Spot-check: with flag off, owner assign creates no notify; enable flag and re-assign → notify appears.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Unexpected silence for Incident owner notify in an env that needed prior always-on behaviour; or admin toggle not persisting.
- **Rollback steps:** PATCH `incident_owner_assignment_notify` to `enabled=true` (seconds); or revert merge commit and redeploy. No DB unwind.
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack
- Unit: default-off evaluate, gate bite, inventory polarity/honesty, GET seed, FE toggle presence
- Change Ledger: this body

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Additive notify flag (no schema migration); Inventory GET does not seed
- [ ] **Gate 2:** CI green on the PR
- [ ] **Gate 3:** Staging verification (after merge/deploy)
- [x] **Gate 4:** Canary N/A — admin toggle + single producer gate
- [ ] **Gate 5:** DONE = tip LIVE after merge — not claimed at open
