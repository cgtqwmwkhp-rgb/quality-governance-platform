# Change Ledger (GT-BRAND-MARK)

## 1) Summary
- **Feature / Change name:** Replace Lucide shield brand mark with Plantexpand interlocking-octagon template recolored for QGP
- **User goal (1–2 lines):** Keep the QGP lime/PRO chrome, but use the company interlocking-octagon mark with brand greens instead of burgundy/charcoal.
- **In scope:** `BrandMark` / `BrandMarkTile` SVG component; shell sidebar logo; auth and portal brand headers that previously used the shield-in-gradient tile.
- **Out of scope:** Favicon/PWA icons, marketing site, Lucide `Shield` icons used as feature/nav glyphs, color-token redesign beyond the mark.
- **Feature flag / kill switch:** None (pure presentation).

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `frontend/src/components/BrandMark.tsx`; `Layout.tsx`; `Login.tsx`; `ForgotPassword.tsx`; `ResetPassword.tsx`; `PortalLogin.tsx`; `Portal.tsx`.
- **Backend (handlers/services):** None.
- **APIs (endpoints changed/added):** None.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None.
- **Database (migrations/entities/indexes):** None.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI-only mark swap; no API or data contract changes.
- **Tolerant reader / strict writer applied?** N/A.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy (DB):** Not applicable.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** Sidebar QGP branding uses the interlocking-octagon company template (not Lucide Shield).
- [x] **AC-02:** Template colors map burgundy→brand lime and charcoal→deep green; QGP PRO badge/gradient chrome remains.
- [x] **AC-03:** Login, forgot/reset password, portal login, and portal header brand tiles use the same mark.
- [x] **AC-04:** Allowlist exclusive — brand mark component + listed brand header call sites + this Change Ledger only.

## 5) Testing Evidence (link to runs)
- [x] Frontend typecheck: `npx tsc --noEmit` in `frontend/` — passed.
- [ ] Full CI suite: pending PR CI.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Authenticated shell shows QGP + PRO with recolored company mark in the sidebar.
- [x] **CUJ-02:** Unauthenticated login and portal login surfaces show the same mark.

## 7) Observability & Ops
- **Logs:** None.
- **Metrics:** None.
- **Alerts:** None.
- **Runbook updates:** None.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Load login and dashboard; confirm mark renders and PRO badge still uses gradient-brand.
- **Canary plan:** Normal frontend SWA deploy path.
- **Prod post-deploy checks:** Visual check of sidebar + login brand mark.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Brand mark rendering regression or accessibility label issues.
- **Rollback steps:** Revert this PR and redeploy prior frontend.
- **Owner:** Quality Governance Platform team.

## 10) Evidence Pack (links)
- **PR:** Added after PR creation.
- **CI run(s):** Added by GitHub Actions after PR creation.
- **Staging deploy evidence:** Pending deployment.
- **Canary evidence:** Pending deployment.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock, acceptance criteria, and Change Ledger complete.
- [x] **Gate 1:** No API/data contract or migration impact.
- [x] **Gate 2:** Frontend typecheck passes locally.
- [ ] **Gate 3:** PR CI green.
- [ ] **Gate 4:** Staging verification complete.
- [ ] **Gate 5:** Production verification complete.
