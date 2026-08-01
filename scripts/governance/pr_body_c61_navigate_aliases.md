# Change Ledger (CL-UX-REGISTRY-C61-ALIASES)

## 1) Summary
- **Feature / Change name:** Register seven App.tsx `<Navigate>` legacy staff alias routes in PAGE_REGISTRY (C-61 next)
- **User goal (1-2 lines):** Stop the UX link audit treating golden-thread UAT legacy paths (`/capa`, `/evidence`, `/exceptions`, `/knowledge-bank`, `/my-work`, `/admin/campaign-compliance`, `/admin/hsec-inbox`) as "Route not in registry" dead ends while they honestly redirect to registered canonical pages.
- **In scope:** Seven verified Navigate-only aliases in `frontend/src/App.tsx`; `PAGE_REGISTRY.yml` P2 admin entries; unit-test guards; summary count correction
- **Out of scope:** Nested portal page components (#1484); catch-alls (`/*`, `/portal/*`, `/risks/*`); staff detail/execute builders; Copilot; B-10 baselines; changing redirect targets
- **Feature flag / kill switch:** N/A — registry documentation only

## 2) Impact Map (what changed)
- **Frontend:** None (aliases already mounted)
- **Backend / APIs / Schemas / Database:** None
- **Workflows:** UX link audit allowlist via `docs/ops/PAGE_REGISTRY.yml`
- **Docs / tests:** `PAGE_REGISTRY.yml` (+7 P2 aliases); `tests/unit/test_page_registry_nav_routes.py`

### Route census (tip `60442106` / #1481)
| Route | Component | Redirects to | Action |
|-------|-----------|--------------|--------|
| `/capa` | `Navigate` | `/actions?sourceType=capa` | Registered P2 |
| `/my-work` | `Navigate` | `/actions?view=mine` | Registered P2 |
| `/evidence` | `Navigate` | `/compliance` | Registered P2 |
| `/knowledge-bank` | `Navigate` | `/documents` | Registered P2 |
| `/exceptions` | `Navigate` | `/knowledge-exceptions` | Registered P2 |
| `/admin/campaign-compliance` | `Navigate` | `/documents/campaigns` | Registered P2 |
| `/admin/hsec-inbox` | `Navigate` | `/admin/hseq-inbox` | Registered P2 |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive registry entries only; no runtime behaviour change
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert this PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Each added route is declared in `frontend/src/App.tsx` as `<Navigate … replace />`
- [x] AC-02: Canonical redirect targets already exist in PAGE_REGISTRY; no invented routes
- [x] AC-03: Alias entries use `auth: jwt_admin`, `criticality: P2`, `component: Navigate`; P0 denominator unchanged (12)
- [x] AC-04: Summary counts corrected to measured totals (85 / 12 / 44 / 29); unit tests lock the seven alias paths + summary arithmetic
- [x] AC-05: No overlap with #1484 portal page registrations (`/portal/work|reading|tools|van|track/:ref`)

## 5) Testing Evidence (link to runs)
- [x] Local: `python3.11 -m pytest tests/unit/test_page_registry_nav_routes.py` → **7 passed**
- [x] Local: `python3 scripts/validate_registries.py` → all 3 registries OK
- [ ] PR CI: pending on this PR
- [ ] Post-merge: UX Functional Coverage Gate dead-end count for these paths

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Staff bookmark `/capa` / `/my-work` / `/evidence` / `/knowledge-bank` / `/exceptions` resolves via Navigate without link audit "Route not in registry"
- [x] CUJ-02: Legacy admin paths `/admin/campaign-compliance` and `/admin/hsec-inbox` remain registered P2 aliases under the unit guard
- [x] CUJ-03: P0 count stays 12; aliases do not inflate the critical denominator

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** No change
- **Runbook updates:** None
- **Metrics:** UX dead-end count for these alias paths should drop on the next gated run; P2 expected count rises by 7

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Normal pipeline; post-merge UX Functional Coverage Gate
- **Canary plan:** N/A
- **Prod post-deploy checks:** Normal SHA promote; no special canary

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Registry validation failure or unexpected link-audit regression attributable to these entries
- **Rollback steps:** Revert this PR; redeploy previous SHA if a promote already happened
- **Owner:** David Harris

## 10) Evidence Pack (links)
- Prior C-61 batches: #1425 (password recovery), #1446 (eight Layout routes), #1448 (`/admin/hs-reporting-hours`), #1451 (nine admin residuals), #1484 (nested portal — parallel, no content overlap)
- Tip base: `60442106` (#1481)
- Board: `w4-gate-denominator-is-half-the-app` / Wave 5

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Registry + unit guard only; no product runtime change
- [ ] **Gate 2:** PR CI pending
- [ ] **Gate 3:** Staging UX gate re-run pending after merge
- [x] **Gate 4:** Canary not used
- [x] **Gate 5:** Rollback = revert this PR

## Remaining C-61 decisions (not in this PR)
Census at tip after this PR: **119** App.tsx path attrs, **85** registry, **~34** still unregistered (plus catch-alls).

| Category | Examples | Decision needed |
|----------|----------|-----------------|
| Nested portal pages | `/portal/work`, `/tools`, `/van`, `/reading`, track-by-ref | In flight on #1484 |
| Catch-alls / roots | `/`, `/*`, `/portal/*`, `/risks/*` | Leave out of registry (not pages) |
| Staff detail / execute | `/actions/:id`, `/investigations/:id`, `/documents/:id`, `/safety-assets/:id`, `/risk-register/:riskId`, audit/workforce execute & builders | P1 vs P2 per surface |
| Legacy portal forms | `/portal/report/incident-legacy`, `/portal/report/near-miss-static` | Keep for compat at P2, or remove links/routes? |
| Staff `/help` | `PortalHelp` under staff shell | Register P2, or point staff at `/portal/help` only? |

Do not weaken UX gate scoring; this only removes false-positive dead ends for real Navigate aliases.

Made with [Cursor](https://cursor.com)
