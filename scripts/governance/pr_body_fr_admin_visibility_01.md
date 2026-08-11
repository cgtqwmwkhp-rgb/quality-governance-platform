# Change Ledger (CL-FR-ADMIN-VISIBILITY-01)

> Base: `origin/main` @ `dc31c0bfd` (#1713 Approvals read model, LIVE).
> Frontend Layout discoverability only — no route/RBAC/API/schema change.

## 1) Summary

- **Feature / Change name:** FR-ADMIN-VISIBILITY-01 — Admin hub visible to roles that can already deep-link `/admin`
- **User goal (1–2 lines):** An `admin` / `manager` / `hsec` user who can open `/admin` by URL must also find Admin Console in the sidebar (and header Settings gear), without needing `isSuperuser()` plus `admin_user_management`.
- **Problem:** Layout gated the Admin hub and Settings gear on `isSuperuser() && admin_user_management`, while `App.tsx` `/admin` uses `RequireRole(['admin','manager','hsec'])`. Managers and HSEC could deep-link but had no nav discoverability.
- **In scope:**
  - `Layout.tsx` — Admin hub + Settings gear + pending-lookups badge fetch gate → `hasRole('admin','manager','hsec')`
  - `Layout.test.tsx` — role-aligned positive/negative coverage (not flag/superuser-only)
- **Out of scope / deliberately not done:**
  - No change to `App.tsx` route guards or per-child admin page RBAC
  - No change to `/admin/users` still requiring superuser + `admin_user_management`
  - No filtering of Admin hub children by finer per-route roles (deep links already enforce)
  - UX Coverage Gate HOLD — ignored per conveyor instruction
- **Feature flag / kill switch:** None for hub discoverability. `admin_user_management` remains the kill switch for User Management in `App.tsx` only.

## 2) Impact Map (what changed)

- **Frontend:** `frontend/src/components/Layout.tsx` — replace `canManageUsers && adminUserManagementEnabled` with `canAccessAdmin = hasRole('admin','manager','hsec')` for Admin hub, header Settings target, and pending safety-lookups polling gate.
- **Tests:** `frontend/src/components/__tests__/Layout.test.tsx` — Settings gear + Admin hub assertions follow role gate (including non-superuser admin-capable and superuser-without-role negative).
- **Backend / APIs / Database / Config:** None.
- **Dependencies:** None.
- **Docs:** This Change Ledger.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive discoverability. Roles already authorised for `/admin` gain nav; others unchanged.
- **Breaking changes:** None for APIs/data. UI: Admin hub may appear for manager/hsec who previously only deep-linked.
- **Migration plan:** N/A.
- **Rollback strategy:** Revert merge commit; redeploy prior tip. No schema/flag/data.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Admin Console discoverability | Superuser + `admin_user_management` only | Matches `/admin` roles: admin, manager, hsec |
| Header Settings → `/admin` | Same superuser+flag gate | Same role gate as hub |
| `/admin` route RBAC | `RequireRole(['admin','manager','hsec'])` | Unchanged |
| User Management kill switch | Flag gated whole Admin hub | Flag still gates `/admin/users` only (App.tsx) |
| Authz surface | Nav tighter than route (mismatch) | Nav aligned with deep-link capability |

## 4) Acceptance Criteria (AC)

- [x] **AC-01:** Admin hub renders when `hasRole('admin','manager','hsec')` is true, even if `isSuperuser()` is false and `admin_user_management` is off.
- [x] **AC-02:** Admin hub does not render when those roles are absent (even if `isSuperuser()` is true / flag on).
- [x] **AC-03:** Header Settings gear links to `/admin` for admin-capable roles and `/dashboard` otherwise.
- [x] **AC-04:** `Layout.test.tsx` covers AC-01–AC-03 without weakening existing hub structure tests.
- [x] **AC-05:** Change Ledger body present for `pnpm validate:pr-body` / gate checklist.

## 5) Testing Evidence

- [x] Unit — `npx vitest run src/components/__tests__/Layout.test.tsx` → **22 passed**
- [ ] Lint / typecheck / full CI — after PR open
- [ ] Staging / prod LIVE verify — conveyor after merge (do not merge from this PR alone)

## 6) Critical Journeys (CUJ)

- [x] **CUJ-01:** Manager (not superuser) expands Admin → sees Admin Console → `/admin` (route guard already allows).
- [x] **CUJ-02:** Non-admin role has no Admin hub; Settings gear → `/dashboard`.
- [x] **CUJ-03:** Superuser without admin/manager/hsec role does not gain Admin hub solely from `isSuperuser()`.

## 7) Observability & Ops

- **Logs / metrics / alerts:** No change
- **Runbook:** N/A — UI discoverability only

## 8) Release Plan

- Squash-merge to `main` only via conveyor allowlist → Main CI → Azure deploy → verify ACA image tip SHA + health on prod FQDN.
- **Do not merge from this PR author path** — leave for conveyor.

## 9) Rollback Plan

- **Trigger:** Wrong roles see Admin hub, or admin-capable roles lose hub.
- **Steps:** Revert squash on `main`; redeploy prior tip via standard CD.
- **Owner:** Platform / conveyor

## 10) Evidence Pack

- CI / staging / prod tip: linked after merge and LIVE verify
- Local unit: Layout.test.tsx 22/22 green on this branch

---

# Gate Checklist

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — UI nav only; route RBAC untouched
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A — frontend nav)
- [x] **Gate 5:** Rollback = revert; no flag/data
- [~] **UX Coverage Gate:** HOLD — ignored per FR instruction
