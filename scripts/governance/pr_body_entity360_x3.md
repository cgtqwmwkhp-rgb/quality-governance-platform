# Change Ledger (CL-ENTITY360-X3)

## 1) Summary
- **Feature / Change name:** X-3 — Satellite Connections adoption
- **User goal (1–2 lines):** When `entity_360` and nested `entity_360_satellites` are on, Audits/CAPA · Incidents · Risk treatments · CS evidence share the same Entity360 Connections strip and producers; Training deferred (UUID hop contract).
- **In scope:** `ComplianceEvidenceProducer` (origin `cel`); CaseLink CAPA bi-links + audit_finding subject; href `clause_evidence_href`; FE `requiresSatellites` gate; mounts on IncidentDetail, RiskProfile, ActionDetail (capa), Audits highlighted finding; unit + Vitest
- **Out of scope:** Enabling `entity_360` / `entity_360_satellites`; Training/induction mounts; CEL on documents (id-namespace collision); hop contract `source_key` widening; changing frozen risk-upstream `audit_finding_href`
- **Feature flag / kill switch:** `entity_360_satellites` / `ENTITY_360_SATELLITES_ENABLED` — **default OFF** (X-0 pre-registered). Parent `entity_360` must also be on for satellite mounts. Flag-off → CEL skipped; CAPA/finding extensions idle; strip absent on satellite pages.

## Conveyor / merge gate
- Depends on **JL-3** tip (`c54c4d8`) LIVE on main.
- Tip base: `origin/main` at/after `c54c4d8`.
- Do **not** arm auto-merge until CI green on this PR.
- Do **not** enable `entity_360` or `entity_360_satellites` in staging/prod as part of this merge.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `Entity360Strip` + helpers (`requiresSatellites` / `shouldShowSatelliteConnections`); mounts on IncidentDetail, RiskProfile, ActionDetail (capa only), Audits highlighted finding card
- **Backend (handlers/services):** `ComplianceEvidenceProducer`; CaseLink CAPA + audit_finding branches; registry registration; `clause_evidence_href`; hop permission `evidence_link`
- **APIs (endpoints changed/added):** None (existing Entity360 routes)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None — hop contract unchanged
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** Wiring only for existing `entity_360_satellites` (no new flags; remains default off)
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive producers behind default-off nested flag; DocumentDetail / JobLifecycle Connections unchanged (`entity_360` only)
- **Tolerant reader / strict writer applied?** Yes — empty lists always present; CEL confidence clamped to hop 0..1 or dropped
- **Breaking changes:** None while flags off. Removed unused int `"clause"` href builder (nothing called it; string clause ids use `clause_evidence_href`)
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB — set `ENTITY_360_SATELLITES_ENABLED=false`

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Satellite Connections UX | Document / job only | Incident · Risk · CAPA · finding card mounts behind nested satellites flag |
| CAPA ↔ source bi-link | Risk downstream empty | CAPA hops via `case_link` when satellites on |
| CS evidence in Entity360 | `cel` origin reserved unused | CEL producer emits `evidence_link` hops (not documents — id collision) |
| Training Connections | N/A | Deferred — InductionRun UUID vs int hop/route |
| Href construction | Int clause builder dead | `clause_evidence_href(str)` only; registry-only |
| Flag defaults | Pre-registered off | Untouched — still default off |
| Authz tokens / admin grant | 84 | Unchanged (`evidence_link` auth-only like `capa`) |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `entity_360_satellites` off → CEL skipped; CAPA/finding extensions idle; satellite strips hidden (no fetch)
- [x] AC-02: Both flags on → Incident / Risk / CAPA / highlighted finding show Connections word via `Entity360Strip`
- [x] AC-03: CAPA↔source and risk treatment hops bidirectional where int-keyed sources exist
- [x] AC-04: CEL hops use `evidence_link` + `clause_evidence_href`; never string-built at call sites
- [x] AC-05: DocumentDetail / JobLifecycle still gate on `entity_360` alone
- [x] AC-06: No migration; flags not enabled in any environment by this PR
- [x] AC-07: BE unit + FE Vitest cover flag gating and producers

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (BE) — `tests/unit/test_entity_360_x3_satellites.py` + X-1 suite — **22 passed** locally
- [x] Unit (FE) — Entity360Strip helpers/satellites + ActionDetail + RiskProfile — **passed** locally
- [ ] Integration — CI as applicable
- [ ] Contract — CI as applicable
- [ ] E2E Smoke — staging bake when flags enabled

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flags on → CAPA detail Connections shows source hop; risk Connections shows treatment CAPAs
- [x] CUJ-02: Flags off → satellite strips absent; DocumentDetail Connections still `entity_360`-only
- [x] CUJ-03: CEL nonconformity relation is not labelled as evidence

## 7) Observability & Ops
- **Logs:** Existing Entity360 producer error → source `error`
- **Metrics:** No new metrics
- **Alerts:** None new
- **Runbook updates:** Keep both Entity360 flags off until bake; enable `entity_360` before `entity_360_satellites`

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; both flags remain off unless bake
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA image tip SHA; `/health` / version; confirm satellites still off unless signed enablement

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Satellite Connections 500s with flag on; false CEL conformance claims; unexpected satellite strip traffic with flag off
- **Rollback steps:** Set `ENTITY_360_SATELLITES_ENABLED=false` (and/or `ENTITY_360_ENABLED=false`); redeploy prior image / revert squash
- **Owner:** Platform Engineering (Entity360 X-3) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (nested flag; CEL evidence_link; CAPA case_link; no hop contract widen)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked) — tip SHA; flags remain off
- [ ] **Gate 4:** Canary healthy (if used) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flags off until bake)

Made with [Cursor](https://cursor.com)
