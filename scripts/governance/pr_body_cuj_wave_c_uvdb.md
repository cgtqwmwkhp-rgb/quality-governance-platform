# Change Ledger — CUJ Wave C UVDB / Achilles downstream lift

## change ledger
- UVDB specialist home: CAPA + Risk deep-links (scoped query params)
- auditRef miss: recovery CTAs including import-review when `runId`/`jobId` present
- SPA `Link` navigation to import review (no full-page `window`/`<a href>` reload)
- assuranceHubHelpers: Achilles / UVDB `source=` filter parity with customer audits
- Reconciliation fetch on UVDB home with honesty labels + proof_matrix (uvdb_sync) chips
- Promote view_links carry `runId`/`jobId`/`import_review` for closed-loop recovery
- Planet Mark / UVDB e2e: un-skipped; working route harness in unit + smoke
- Playwright CUJ: import → home handoff + CAPA/Risk + miss recovery + proof chips
- Promote / uvdb_sync outcome metrics: in-process counters + OTel tags (not log-only)
- Unit tests for hand-offs and promotion metrics

## summary
Closes residual dual-lens gaps (~6.9 → aim ≥8.5 / ~9.5 honesty+closed-loop+proof) on the Achilles/UVDB specialist surface. Exclusive allowlist only — zero overlap with open PRs #907–#911. #853 human unlocks (SMTP/PagerDuty/secrets) remain parked; never invented.

## impact map
- **Frontend:** `UVDBAudits.tsx` hand-offs, miss recovery, reconciliation panel; `assuranceHubHelpers.ts` Achilles/UVDB source filter + deep-link builders
- **Backend:** `external_audit_promotion_service.py` promote + uvdb_sync outcome counters / OTel tags + summary fields
- **Tests:** UVDBAudits unit, assuranceHubHelpers unit, promotion metrics unit, Playwright CUJ, planetmark/uvdb e2e harness
- **Docs:** this Change Ledger PR body
- **Out of scope:** Actions/Incident/Investigation/Complaints/near-miss, Layout/App/i18n dumps, Audits.tsx / AuditExecution.tsx, #853 SMTP/PD

## compatibility
- Additive only. Existing `/audits?source=customer` behaviour unchanged.
- New `/audits?source=achilles` and `/audits?source=uvdb` filter via shared helper (Audits page already calls `filterAuditsByAssuranceSource`).
- Promotion summary gains `uvdb_sync_status` / `uvdb_audit_id` fields (backward compatible).

## acceptance criteria
- [x] AC-01: UVDB home exposes CAPA (`/actions?sourceType=audit_finding`) and Risk (`/risk-register?auditOnly=1&auditRef=`) deep-links
- [x] AC-02: auditRef miss is not a dead end — recovery CTAs present (incl. import review when runId/jobId present)
- [x] AC-03: Import review uses react-router `Link`; Playwright CUJ covers handoff + CAPA/Risk + miss + proof
- [x] AC-04: Achilles/UVDB assurance source filter parity in `assuranceHubHelpers`
- [x] AC-05: Promote / uvdb_sync outcomes increment observable counters (unit-tested)
- [x] AC-06: Planet Mark / UVDB e2e module no longer globally skipped
- [x] AC-07: Reconciliation panel shows proof_matrix (incl. uvdb_sync) and import-review handoff

## testing evidence
- Frontend unit: `UVDBAudits.test.tsx`, `assuranceHubHelpers.test.ts`
- Backend unit: `tests/unit/test_external_audit_promotion_metrics.py`
- Playwright: `frontend/tests/e2e/uvdb-import-downstream-cuj.spec.ts`
- Harness: `tests/e2e/test_planetmark_uvdb_e2e.py`

## critical journeys
- CUJ-01: Import promote → UVDB home (`?auditRef=`) → reconciliation panel → Import review SPA link
- CUJ-02: UVDB home → CAPA Actions + scoped Risk Register; auditRef miss → recovery CTAs

## observability
- In-process counters: `promote:<outcome>`, `uvdb_sync:<outcome>` via `get_promotion_outcome_counters()`
- OTel: `external_audit_import.promote` with outcomes including `uvdb_sync:synced|missing|failed|n_a|already_synced`
- Job summary: `uvdb_sync_status`, `uvdb_audit_id`
- UI honesty: reconciliation panel labels ready / partial / unavailable

## release plan
1. Squash-merge to main after CI green (do not merge from this agent)
2. Staging auto-deploy via CI workflow_run
3. Confirm staging tip + `/healthz` 200 (2×)
4. Force-deploy production with full 40-char `release_sha` in freeze window when approved

## rollback plan
1. Revert squash commit on main
2. Redeploy previous known-good SHA via production workflow_dispatch
3. Verify `/api/v1/meta/version` matches rollback SHA

## evidence pack
- AC-01..06 covered by unit + Playwright + harness listed above
- Gate ledger: this file (`scripts/governance/pr_body_cuj_wave_c_uvdb.md`)
- Exclusive allowlist respected (no #907–#911 files; #853 parked)

## gate checklist
- [x] Gate 0: Scope lock + Change Ledger complete
- [x] Gate 1: Exclusive allowlist (UVDBAudits, helpers, e2e, promotion metrics, ledger)
- [ ] Gate 2: CI required checks (post-push)
- [ ] Gate 3: Staging tip == SHA
- [ ] Gate 4: Prod tip == SHA (human)
- [x] Gate 5: Evidence recorded in this PR body
