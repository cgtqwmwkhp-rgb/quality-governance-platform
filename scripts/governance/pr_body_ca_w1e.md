# Change Ledger (CL-CA-W1e)

## File allowlist (exclusive)

- `src/domain/services/compliance_automation_service.py`
- `src/api/routes/compliance_automation.py`
- `tests/unit/test_riddor_prepare_honesty.py`
- `tests/e2e/test_compliance_automation.py`
- `tests/smoke/test_phase3_phase4_smoke.py`
- `frontend/src/pages/ComplianceAutomation.tsx`
- `frontend/src/pages/complianceAutomationHelpers.ts`
- `frontend/src/pages/__tests__/ComplianceAutomation.test.tsx`
- `frontend/src/pages/__tests__/complianceAutomationHelpers.test.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_ca_w1e.md`

**Zero overlap** with parallel lanes: `RiskProfile*`, `RiskHeatMap*`, `Actions.tsx`, `Audits.tsx`, `Layout.tsx`, `App.tsx`, `client.ts`, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 CA-W1e — Monitoring delivery (incident→pack persistence + Watch Run/Refresh honesty)
- **User goal:** Operators on Monitoring see real RIDDOR draft packs persisted from Incidents in the register, with live HSE portal links; Run watch refreshes the full Changes inbox and surfaces honest errors.
- **In scope:** Persist prepare/list/submit against existing `riddor_submissions` table; register UI rows; Watch Run → full inbox refresh + error banner; en/cy soft-union; unit/e2e/smoke/vitest updates
- **Out of scope:** Production HSE gateway filing; Alembic; App/Layout/client spines; RiskProfile/RiskHeatMap; full i18n sweep of every Monitoring label
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| `POST /riddor/prepare/{id}` | Ephemeral stub (`preparation_stub`, `persisted: false`) | Loads incident, upserts `RIDDORSubmission` draft pack (`draft_pack`, `persisted: true`) |
| `GET /riddor/submissions` | Always empty | Tenant register of persisted packs |
| `POST /riddor/submit/{id}` | Fake HSE success-looking stub without DB | Updates pack to `awaiting_hse_filing`; `gateway: not_connected` honesty |
| RIDDOR tab UI | Count-only / empty | Pack rows with incident + HSE deep-links |
| Changes → Run watch | Refreshed impacts only; toast-only errors | Full inbox refresh + `watchError` banner |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive on existing `riddor_submissions` table (no migration)
- **Breaking changes:** Prepare/submit now require a real tenant incident (404 otherwise); prepare status string `preparation_stub` → `draft_pack`; submit local ref prefix `QGP-RIDDOR-`
- **Rollback strategy:** Revert squash merge (rows left in `riddor_submissions` are harmless drafts)

## 4) Acceptance Criteria (AC)

- [x] AC-01: Certificates + RIDDOR tabs remain on Monitoring; HSE portal/guide links live
- [x] AC-02: `prepare` persists a draft pack for a real incident (`persisted: true`, status `draft_pack`)
- [x] AC-03: `GET /riddor/submissions` returns persisted packs (honest empty when none)
- [x] AC-04: Register UI renders pack rows with Open incident + HSE portal links
- [x] AC-05: `submit` remains gateway-stub honesty (`gateway: not_connected`, not treated as HSE-filed)
- [x] AC-06: Run watch refreshes Changes inbox and surfaces errors in-page
- [x] AC-07: Unit + vitest + e2e/smoke contracts updated

## 5) Testing Evidence

- [x] Unit — `tests/unit/test_riddor_prepare_honesty.py`
- [x] Vitest — `ComplianceAutomation.test.tsx`, `complianceAutomationHelpers.test.ts`
- [x] E2E/smoke contracts updated for persist path
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Fresh tenant — RIDDOR register empty with honest copy (not “already filed”)
- [x] CUJ-02: Prepare pack from incident — pack appears in register with HSE link
- [x] CUJ-03: Submit stub — pack status `awaiting_hse_filing`, gateway not connected
- [x] CUJ-04: Run watch failure — Changes error banner + toast (no silent success)

## 7) Observability & Ops

- **Playwright hooks:** `monitoring-riddor-register`, `monitoring-riddor-empty`, `monitoring-riddor-packs`, `monitoring-riddor-pack-{id}`, `monitoring-riddor-incident-{id}`, `monitoring-riddor-hse-{id}`, `monitoring-riddor-refresh`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging tip smoke `/compliance-automation` → RIDDOR register + Changes Run watch

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation
- Builds on: #1043 RIDDOR/HSE honesty, #1064 CA-W1d Changes inbox, certificates lineage

---

# Follow-ons (deferred)

| Item | Rationale |
|------|-----------|
| Production HSE RIDDOR gateway integration | External filing; keep QGP as draft/register only |
| IncidentDetail “Prepare RIDDOR pack” CTA | FE surface for prepare API (API ready) |
| Full Monitoring i18n sweep of remaining hard-coded strings | Nice-to-have; soft-union done for new RIDDOR keys |

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected (no App/Alembic/RiskProfile/RiskHeatMap/client)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `python3.11 -m pytest tests/unit/test_riddor_prepare_honesty.py -q`
- [ ] `cd frontend && npx vitest run src/pages/__tests__/ComplianceAutomation.test.tsx src/pages/__tests__/complianceAutomationHelpers.test.ts`
- [ ] Manual: `/compliance-automation` RIDDOR empty honesty
- [ ] Manual: prepare pack for an incident → register row + HSE link
- [ ] Manual: Run watch with upstream failure → error banner
