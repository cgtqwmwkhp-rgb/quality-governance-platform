# Change Ledger (CL-UX-REGISTRY-C61-RESIDUAL)

## 1) Summary
- **Feature / Change name:** Register nine more real linked App.tsx routes missing from PAGE_REGISTRY (C-61 residual)
- **User goal (1-2 lines):** Stop the UX link audit scoring Layout admin nav, AdminDashboard tiles, and asset-health deep-links as "Route not in registry" dead ends after #1446/#1448.
- **In scope:** Nine verified `App.tsx` routes with existing page components and live links; `PAGE_REGISTRY.yml` P1 entries; unit-test allowlist extension; summary count correction
- **Out of scope:** Full C-61 criticality triage; Navigate-only aliases (`/admin/campaign-compliance`, `/admin/hsec-inbox`); `/portal/tools|/van|/work` (linked but no App.tsx route — real dead ends, not registry false positives); Dependabot; allowlist edits
- **Feature flag / kill switch:** N/A — registry documentation only

## 2) Impact Map (what changed)
- **Frontend:** None (routes already mounted)
- **Backend / APIs / Schemas / Database:** None
- **Workflows:** UX link audit allowlist via `docs/ops/PAGE_REGISTRY.yml`
- **Docs / tests:** `PAGE_REGISTRY.yml` (+9 P1); `tests/unit/test_page_registry_nav_routes.py`

### Route census (tip `faff5a38`)
| Route | Component | Linked from | Action |
|-------|-----------|-------------|--------|
| `/admin/users` | `AdminUserManagement` | Layout, AdminDashboard | Registered P1 |
| `/admin/lookups` | `LookupTables` | Layout, AdminDashboard, Complaints, SafetyAssetRegister | Registered P1 |
| `/admin/hseq-inbox` | `HsecQuestionInbox` | Layout, AdminDashboard | Registered P1 |
| `/admin/notifications` | `NotificationSettings` | Layout, AdminDashboard | Registered P1 |
| `/admin/partner-webhooks` | `PartnerWebhooks` | Layout, AdminDashboard | Registered P1 |
| `/admin/library-roles` | `LibraryRoles` | AdminDashboard | Registered P1 |
| `/admin/engineer-groups` | `EngineerGroups` | AdminDashboard | Registered P1 |
| `/workforce/competence-gaps` | `CompetenceGaps` | Layout | Registered P1 |
| `/safety-assets/analytics` | `AssetHealthAnalytics` | AssetHealthHubTile, PulseTrendsStrip, OrgCommandStrip | Registered P1 |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive registry entries only; no runtime behaviour change
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert this PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Each added route is declared in `frontend/src/App.tsx` with an existing page component
- [x] AC-02: Each added route is linked from Layout and/or AdminDashboard / hub tiles (census above); no invented routes
- [x] AC-03: `admin_routes` entries use `auth: jwt_admin`, `criticality: P1`; P0 denominator unchanged (12)
- [x] AC-04: Summary counts corrected to measured totals (78 / 12 / 44 / 22); unit tests lock Layout + hub paths

## 5) Testing Evidence (link to runs)
- [x] Local: `pytest tests/unit/test_page_registry_nav_routes.py` — 4 passed
- [x] Local: `python scripts/validate_registries.py` — all 3 registries OK
- [ ] PR CI: pending on this PR
- [ ] Post-merge: UX Functional Coverage Gate dead-end count for these paths

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Staff open Layout admin nav targets (`/admin/users`, `/admin/lookups`, `/admin/hseq-inbox`, `/admin/notifications`, `/admin/partner-webhooks`) without link audit flagging "Route not in registry"
- [x] CUJ-02: AdminDashboard tiles for library roles / engineer groups and asset-health analytics deep-link remain registered staff P1 routes under the unit guard
- [x] CUJ-03: Workforce competence-gaps Layout link resolves to a registered route matching App.tsx

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** No change
- **Runbook updates:** None
- **Metrics:** UX dead-end count for these paths should drop on the next gated run

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Normal pipeline; post-merge UX Functional Coverage Gate
- **Canary plan:** N/A
- **Prod post-deploy checks:** Normal SHA promote; no special canary

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Registry validation failure or unexpected link-audit regression attributable to these entries
- **Rollback steps:** Revert this PR; redeploy previous SHA if a promote already happened
- **Owner:** David Harris

## 10) Evidence Pack (links)
- Prior C-61 batches: #1446 (eight Layout routes), #1448 (`/admin/hs-reporting-hours`)
- Tip base: `faff5a38` (#1450)
- This PR: (filled by GitHub on create)

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Registry + unit guard only; no product runtime change
- [ ] **Gate 2:** PR CI pending
- [ ] **Gate 3:** Staging UX gate re-run pending after merge
- [x] **Gate 4:** Canary not used
- [x] **Gate 5:** Rollback = revert this PR

## Residuals
- `/portal/tools`, `/portal/van`, `/portal/work` are linked from Dashboard/Portal but have no matching `App.tsx` route — real dead ends, not C-61 false positives; needs a product route or link removal, not registry.
- Navigate aliases `/admin/campaign-compliance` → `/documents/campaigns` and `/admin/hsec-inbox` → `/admin/hseq-inbox` intentionally not registered as pages.
- Other App.tsx admin leaves without current Layout/Dashboard links (e.g. `admin/forms/new`) left unregistered until linked.
- B-10 `extra=forbid` backlog (294 schemas) and contract-test board rows `w2-enum-contract` / `w2-closure-parity` scaffolding already exists on main — not in this PR.
- Do not weaken UX gate scoring; this only removes false-positive dead ends for real routes.
