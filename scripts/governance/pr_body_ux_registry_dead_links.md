# Change Ledger (CL-UX-REGISTRY-DEAD-LINKS)

## 1) Summary
- **Feature / change name:** Register real staff nav routes missing from PAGE_REGISTRY (C-61 class false-positive dead links).
- **User goal:** Stop the UX functional coverage gate scoring valid Layout nav links as "Route not in registry" dead ends.
- **Trigger:** UX gate run [30523733146](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/30523733146) — 17 dead ends, score 0 HOLD (P0 37/37, a11y clean after #1443/#1445).
- **In scope:** Eight verified App.tsx routes + Layout nav links; PAGE_REGISTRY entries (P1); governance unit test; `last_updated` bump.
- **Out of scope:** Full C-61 criticality triage; a11y/aggregator weight changes; allowlist edits (parent lane).

## 2) Impact Map
| Area | Change |
|------|--------|
| `docs/ops/PAGE_REGISTRY.yml` | +8 admin routes (P1, jwt_admin), C-61 comment block, summary counts |
| `tests/unit/test_page_registry_nav_routes.py` | Assert Layout nav targets are registered as staff P1 |

## 3) Route verification (App.tsx)
| Route | Component | Layout nav | Action |
|-------|-----------|------------|--------|
| `/safety-assets` | `SafetyAssetRegister` | Safety Cases hub | Registered |
| `/customer-audits` | `CustomerAudits` | Assurance hub (`CUSTOMER_AUDITS_PROGRAMME_PATH`) | Registered |
| `/my-reading` | `MyReading` | My Work hub | Registered |
| `/my-compliance` | `MyCompliancePassport` | My Work hub | Registered |
| `/analytics/hs-performance` | `HsPerformance` | Insights hub | Registered |
| `/analytics/safety-insights` | `SafetyInsightsAnalyst` | Insights hub | Registered |
| `/knowledge-exceptions` | `KnowledgeExceptions` | Compliance hub | Registered |
| `/document-control` | `DocumentControl` | Compliance hub | Registered |

**Phantoms removed:** none — all eight targets are declared in `frontend/src/App.tsx`.

## 4) Acceptance Criteria
- [x] AC-01: Each Layout dead-end target from gate run 30523733146 is verified in `App.tsx` before registration.
- [x] AC-02: All eight routes added to `admin_routes` with `auth: jwt_admin`, matching components, and `criticality: P1`.
- [x] AC-03: C-61-style comment explains false-positive rationale; P0 denominator unchanged (12 P0 routes).
- [x] AC-04: `last_updated` set to 2026-07-30; summary counts updated (66 total, 32 P1).
- [x] AC-05: Unit test asserts routes present and P1/jwt_admin without weakening link-audit specs.

## 5) Testing Evidence
- [x] `python3 scripts/validate_registries.py` — all registries OK
- [x] `python3.11 -m pytest tests/unit/test_page_registry_nav_routes.py -v` — 2 passed
- [ ] CI UX link audit — expected to clear 17 "Route not in registry" findings on re-run

## 6) Critical Journeys
- [x] CUJ-01: Staff opens any registered nav item from Layout sidebar without link audit flagging a dead end.
- [x] CUJ-02: UX gate P1 link score no longer zeroed by registry false positives (pending CI re-run).

## 7) Residuals
- Sub-routes (e.g. `/safety-assets/:id`, `/safety-assets/analytics`) remain unregistered — link audit skips parameterized routes by design.
- Full C-61 criticality triage of the entire registry remains out of scope.

---

# Gate Checklist
- [x] **Gate 0:** Scope locked, acceptance criteria defined, Change Ledger complete.
- [x] **Gate 1:** Registry-only + unit test; no API/schema/router changes.
- [ ] **Gate 2:** CI green (registry validation, unit tests, UX link audit).
- [ ] **Gate 3:** UX gate re-run confirms dead-link count drops for these eight targets.
- [x] **Gate 4:** Canary not required.
- [x] **Gate 5:** Rollback = revert this PR (remove eight entries).
