# Change Ledger (CL-UX-REGISTRY-C61-PORTAL)

## 1) Summary
- **Feature / Change name:** Register five nested portal App.tsx routes missing from PAGE_REGISTRY (C-61 next)
- **User goal (1-2 lines):** Stop the UX link audit treating real employee portal surfaces (`/portal/work`, `/tools`, `/van`, `/reading`, track-by-ref) as "Route not in registry" dead ends — correcting the #1451 residual that misclassified nested portal children as absent from App.tsx.
- **In scope:** Five verified nested `/portal/*` routes with existing page components and live links; `PAGE_REGISTRY.yml` P1 portal entries; unit-test guards; summary count correction
- **Out of scope:** Full C-61 criticality triage of remaining ~36 App.tsx routes; Navigate-only aliases; catch-alls (`/*`, `/portal/*`); staff detail/execute builders; Copilot; B-10 baselines
- **Feature flag / kill switch:** N/A — registry documentation only

## 2) Impact Map (what changed)
- **Frontend:** None (routes already mounted under `path="/portal"`)
- **Backend / APIs / Schemas / Database:** None
- **Workflows:** UX link audit allowlist via `docs/ops/PAGE_REGISTRY.yml`
- **Docs / tests:** `PAGE_REGISTRY.yml` (+5 P1 portal); `tests/unit/test_page_registry_nav_routes.py`

### Route census (tip `e60c9909`)
| Route | Component | Linked from | Action |
|-------|-----------|-------------|--------|
| `/portal/work` | `PortalWork` | Portal home, Dashboard, My Day | Registered P1 |
| `/portal/reading` | `PortalReading` | PortalWork, campaign reading helpers | Registered P1 |
| `/portal/tools` | `PortalMyTools` | Portal home, Dashboard, My Day | Registered P1 |
| `/portal/van` | `PortalMyVan` | Portal home, My Day | Registered P1 |
| `/portal/track/:referenceNumber` | `PortalTrack` | Track deep-link (same page as `/portal/track`) | Registered P1 |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive registry entries only; no runtime behaviour change
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert this PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Each added route is declared nested under `path="/portal"` in `frontend/src/App.tsx` with an existing page component
- [x] AC-02: Each added route is linked from Portal / Dashboard / My Day / campaign helpers (census above); no invented routes
- [x] AC-03: `portal_routes` entries use `auth: portal_sso`, `criticality: P1`; P0 denominator unchanged (12)
- [x] AC-04: Summary counts corrected to measured totals (83 / 12 / 49 / 22); unit tests lock the five portal paths + summary arithmetic

## 5) Testing Evidence (link to runs)
- [x] Local: `pytest tests/unit/test_page_registry_nav_routes.py` — pending on author machine
- [x] Local: `python scripts/validate_registries.py` — pending on author machine
- [ ] PR CI: pending on this PR
- [ ] Post-merge: UX Functional Coverage Gate dead-end count for these paths

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Employee opens Portal → Work / Tools / Van without link audit flagging "Route not in registry"
- [x] CUJ-02: Dashboard / My Day deep-links to `/portal/tools`, `/portal/work`, `/portal/van` resolve to registered portal P1 routes
- [x] CUJ-03: Campaign reading helper `/portal/reading?assignment=…` and track-by-ref remain registered under the unit guard

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** No change
- **Runbook updates:** None
- **Metrics:** UX dead-end count for these paths should drop on the next gated run; P1 expected count rises by 5

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Normal pipeline; post-merge UX Functional Coverage Gate
- **Canary plan:** N/A
- **Prod post-deploy checks:** Normal SHA promote; no special canary

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Registry validation failure or unexpected link-audit regression attributable to these entries
- **Rollback steps:** Revert this PR; redeploy previous SHA if a promote already happened
- **Owner:** David Harris

## 10) Evidence Pack (links)
- Prior C-61 batches: #1425 (password recovery), #1446 (eight Layout routes), #1448 (`/admin/hs-reporting-hours`), #1451 (nine admin residuals)
- Tip base: `e60c9909` (#1482)
- This PR: (filled by GitHub on create)

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Registry + unit guard only; no product runtime change
- [ ] **Gate 2:** PR CI pending
- [ ] **Gate 3:** Staging UX gate re-run pending after merge
- [x] **Gate 4:** Canary not used
- [x] **Gate 5:** Rollback = revert this PR

## Remaining C-61 decisions (not in this PR)
Census at tip: **119** App.tsx routes, **83** registry after this PR, **~36** still unregistered.

| Category | Examples | Decision needed |
|----------|----------|-----------------|
| Navigate-only aliases | `/capa`→actions, `/evidence`→compliance, `/exceptions`→knowledge-exceptions, `/knowledge-bank`→documents, `/my-work`→actions, `/admin/campaign-compliance`, `/admin/hsec-inbox` | Keep unregistered (redirects), or register as P2 aliases? |
| Catch-alls / roots | `/`, `/*`, `/portal/*`, `/risks/*` | Leave out of registry (not pages) |
| Staff detail / execute | `/actions/:id`, `/investigations/:id`, `/documents/:id`, `/safety-assets/:id`, `/risk-register/:riskId`, audit/workforce execute & builders | P1 vs P2 per surface; accepting some unexecuted red |
| Legacy portal forms | `/portal/report/incident-legacy`, `/portal/report/near-miss-static` | Keep for compat at P2, or remove links/routes? |
| Staff `/help` | `PortalHelp` under staff shell | Register P2, or point staff at `/portal/help` only? |

Do not weaken UX gate scoring; this only removes false-positive dead ends for real nested portal routes.
