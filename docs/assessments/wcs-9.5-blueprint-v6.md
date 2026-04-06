# WCS 9.5 Gap Closure Blueprint v6

**Baseline**: Commit `6193d088` (branch `fix/wcs-9.5-v5`)
**Prior Assessment**: `docs/assessments/world-class-scorecard-2026-04-03.md`
**Target**: ALL 32 dimensions >= 9.5 WCS

## Round 1 Summary: Per-Dimension Gaps

| Dim | Current | Gap | Top Blocker |
|-----|---------|-----|-------------|
| D01 | 5.4 | 4.1 | 8/10 CUJs partial; no external usability testing |
| D02 | 7.2 | 2.3 | 4 missing stories (Button, Card, Input, Badge); no visual regression; no play functions |
| D03 | 7.2 | 2.3 | 7 VPAT "Partially Supports" items; 8 components without axe tests; 5 WCAG unchecked |
| D04 | 7.2 | 2.3 | 6 Lighthouse metrics warn not error; duplicate web-vitals modules |
| D05 | 7.2 | 2.3 | 4 chaos scenarios untested; no PITR drill |
| D06 | 5.4 | 4.1 | DAST not in all-checks; 3 || true in security-scan.yml; 1 security review only |
| D07 | 4.5 | 5.0 | restrict_processing is stub; Art. 18/20 not implemented; DPIA unsigned |
| D08 | 4.5 | 5.0 | compliance-freshness not in all-checks; license-compliance missing entirely |
| D09 | 7.2 | 2.3 | ADR-0003 duplicated; no fitness functions beyond import boundary |
| D10 | 5.4 | 4.1 | ~300 bare HTTPException; top 6 files have 112 |
| D11 | 4.5 | 5.0 | Only 6/55 models with CheckConstraint; 10+ critical models have zero |
| D12 | 7.2 | 2.3 | alembic-check not in all-checks |
| D13 | 7.2 | 2.3 | PagerDuty planned only; no structured alerting webhook |
| D14 | 5.4 | 4.1 | 87 plain-string HTTPExceptions across 24 route files |
| D15 | 5.4 | 4.1 | fail_under=48%; mutation schedule-only; no kill-rate threshold |
| D16 | 7.2 | 2.3 | No golden-freshness CI gate |
| D17 | 7.2 | 2.3 | 5 jobs missing from all-checks needs list |
| D18 | 7.2 | 2.3 | No canary/traffic splitting; post-deploy E2E advisory |
| D19 | 7.2 | 2.3 | env-completeness check advisory (|| echo warning) |
| D20 | 4.5 | 5.0 | license-compliance job entirely missing; SBOM not on releases |
| D21 | 4.5 | 5.0 | 188 type-ignores; 38 modules ignore_errors; radon not gating |
| D22 | 7.2 | 2.3 | docs-lint not in all-checks |
| D23 | 6.0 | 3.5 | PagerDuty 100% planned; 4 TBD/PLACEHOLDER in runbooks |
| D24 | 4.5 | 5.0 | Zero OCC; only 2 with_for_update routes |
| D25 | 7.2 | 2.3 | No auto-scaling tested in CI |
| D26 | 7.2 | 2.3 | Per-tenant cost attribution Phases 2-4 planned |
| D27 | 7.2 | 2.3 | 241 missing Welsh keys; CY_MIN_COVERAGE at 75% |
| D28 | 5.4 | 4.1 | No page_view telemetry; 61% of instruments unwired |
| D29 | 8.0 | 1.5 | ADR-0003 duplication; DORA metrics estimated not measured |
| D30 | 7.2 | 2.3 | apt-get upgrade breaks reproducibility; no SLSA attestation |
| D31 | 4.5 | 5.0 | config-drift-guard trivially narrow (1 string, 4 files) |
| D32 | 5.4 | 4.1 | logs CLI command is stub; no admin CLI integration tests |

## Round 2 Summary: Cross-Cutting Patterns

### Pattern 1: CI Pipeline Regression (CRITICAL)
5 existing jobs NOT in all-checks + license-compliance entirely missing.
**Dimensions affected**: D06, D08, D12, D17, D20, D21, D22
**Fix**: Single edit to ci.yml all-checks needs list + create license-compliance job

### Pattern 2: Error Migration Incomplete
~300 HTTPException + 87 plain-string detail remain across 24 route files.
**Dimensions affected**: D10, D14
**Fix**: Batch migration of top-offender files (evidence_assets, inductions, assessments, form_config, users, standards)

### Pattern 3: Model Constraints Sparse
Only 21 CheckConstraints across 6 files. Zero OCC. 2 pessimistic locks.
**Dimensions affected**: D11, D24
**Fix**: Add CheckConstraints to critical models + OCC on high-write models

### Pattern 4: Frontend Quality Gaps
4 missing stories + 8 missing axe tests + no visual regression + no play functions.
**Dimensions affected**: D02, D03
**Fix**: Create stories, axe tests, add Chromatic/visual regression config

### Pattern 5: Observability Instrumentation Gap
No page_view + 61% unwired instruments + PagerDuty planned.
**Dimensions affected**: D13, D23, D28
**Fix**: Wire remaining metrics, add page_view, document PagerDuty plan

### Pattern 6: Privacy/Compliance Unsigned
DPIA unsigned, Art. 18 stub, Art. 20 not self-service.
**Dimensions affected**: D07, D08
**Fix**: Implement restrict_processing, complete DPIA sign-off

### Pattern 7: Testing Floor at 48%
fail_under=48%, mutation schedule-only, no kill-rate threshold.
**Dimensions affected**: D15
**Fix**: Raise fail_under, improve coverage on uncovered modules

### Pattern 8: Config Drift Guard Trivial
Only 1 forbidden string checked across 4 files.
**Dimensions affected**: D31
**Fix**: Expand to real env-var comparison + Bicep drift detection

---

## Workstreams (10)

### WS-1: CI All-Checks Restoration (D06, D08, D12, D17, D20, D21, D22)
1. Add to all-checks needs: compliance-freshness, radon-complexity, alembic-check, docs-lint, dast-zap-baseline, dependency-review
2. Create license-compliance job (pip-licenses + license-checker) and add to all-checks
3. Verify all 32+ jobs are now gating

### WS-2: Error Migration Completion (D10, D14)
1. Migrate remaining ~87 plain-string HTTPExceptions to DomainError subclasses
2. Priority files: document_control (10), kri (10), planet_mark (8), drivers (7), uvdb (6), tenants (5), auditor_competence (5)
3. Add CI lint rule: grep for `raise HTTPException` in routes → fail if count > 20
4. Target: < 20 raw HTTPExceptions (auth guards and middleware only)

### WS-3: Data Model Hardening (D11, D24)
1. Add CheckConstraints to: incident.py, complaint.py, capa.py, near_miss.py, rta.py, audit.py, assessment.py
2. Add version_id_col (OCC) to: Incident, Complaint, CAPA, RTA, AuditRun (5 high-write models)
3. Add with_for_update to concurrent-write route operations (at least 5 more routes)
4. Create Alembic migration for all new constraints + version columns

### WS-4: Frontend Quality (D02, D03)
1. Create 4 missing stories: Button.stories.tsx, Card.stories.tsx, Input.stories.tsx, Badge.stories.tsx
2. Add axe tests for 8 uncovered components: Textarea, ThemeToggle, Tooltip, Avatar, SetupRequiredPanel, LoadingSkeleton, SkeletonLoader, LiveAnnouncer
3. Add play functions to interactive stories (Dialog, AlertDialog, DropdownMenu, Select, Tabs)
4. Add aria-invalid + aria-describedby to all form controls
5. Configure Chromatic or Storybook visual snapshot CI step

### WS-5: Privacy & Compliance (D07, D08)
1. Implement restrict_processing: add processing_restricted column to Incident, Complaint, NearMiss, RTA models; implement real DB write in gdpr_service.py
2. Implement data portability self-service: GET /api/v1/privacy/my-data
3. Complete DPIA sign-off: check decision box, add reviewer names and dates
4. Add retention job metrics + audit entries to cleanup_tasks.py

### WS-6: Observability & Analytics (D13, D23, D28)
1. Wire remaining 11 unwired metrics from event catalog
2. Add page_view telemetry via router listener in frontend
3. Wire auth.login/auth.logout/auth.failures metrics
4. Document PagerDuty integration plan with ADR and timeline
5. Fix 4 remaining TBD/PLACEHOLDER items in runbooks

### WS-7: Testing Uplift (D15, D16)
1. Raise fail_under from 48 to 52 (incremental target)
2. Add golden-freshness CI gate (hash validation of golden JSONs)
3. Add 5 missing CUJ E2E tests (cuj03, cuj05, cuj07, cuj08, cuj10)
4. Fix CUJ-02 source_id assertion (remove pass-through)

### WS-8: Performance & Lighthouse (D04, D25)
1. Promote 6 warn metrics to error in root lighthouserc.json
2. Promote speed-index to error in frontend/lighthouserc.json
3. Deduplicate web-vitals modules (consolidate to one)
4. Add per-route SLO assertions to locustfile.py

### WS-9: Configuration & Environment Parity (D19, D30, D31)
1. Expand config-drift-guard: compare .env.example keys across environments
2. Make env-completeness check blocking (remove || echo warning)
3. Remove apt-get upgrade from Dockerfile production stage
4. Expand Bicep template to include Key Vault, Redis, ACR
5. Add Bicep what-if diff step to CI

### WS-10: Governance & Supportability (D09, D26, D27, D29, D32)
1. Consolidate ADR-0003 (remove duplicate from docs/ root)
2. Add ADR for data retention + GDPR decisions
3. Raise CY_MIN_COVERAGE from 75% to 88%
4. Translate remaining 241 Welsh keys
5. Implement real logs CLI command (Azure Monitor query)
6. Add admin CLI integration tests
7. Add runbook links to /diagnostics endpoint output

## Dependency Graph

```
WS-1 (CI all-checks) ← no dependencies, do FIRST
  ↓
WS-2 (Error migration) ← depends on WS-1 (new lint gate)
WS-3 (Data model) ← independent, parallelizable
WS-4 (Frontend) ← independent, parallelizable
WS-5 (Privacy) ← WS-3 partial (new columns need migration)
WS-6 (Observability) ← independent
WS-7 (Testing) ← WS-2 parallel, WS-3 parallel
WS-8 (Performance) ← independent
WS-9 (Config/Env) ← independent
WS-10 (Governance) ← independent
```

## Estimated Impact per Workstream

| WS | Dims Uplifted | Est. WCS Gain | Priority |
|----|---------------|---------------|----------|
| WS-1 | D06,D08,D12,D17,D20,D21,D22 | +1.5 avg across 7 dims | P0 |
| WS-2 | D10,D14 | +2.0 avg across 2 dims | P0 |
| WS-3 | D11,D24 | +2.5 avg across 2 dims | P0 |
| WS-5 | D07,D08 | +2.5 avg across 2 dims | P0 |
| WS-4 | D02,D03 | +1.5 avg across 2 dims | P1 |
| WS-6 | D13,D23,D28 | +1.5 avg across 3 dims | P1 |
| WS-7 | D15,D16 | +1.5 avg across 2 dims | P1 |
| WS-8 | D04,D25 | +1.0 avg across 2 dims | P2 |
| WS-9 | D19,D30,D31 | +1.5 avg across 3 dims | P2 |
| WS-10 | D09,D26,D27,D29,D32 | +1.0 avg across 5 dims | P2 |

## Non-Code Items (Cannot implement but must document plans)

| Item | Dimension | What's Needed |
|------|-----------|---------------|
| External usability testing | D01 | Recruit 5+ external users |
| External penetration test | D06 | Engage vendor per pentest-plan.md |
| PagerDuty integration | D13, D23 | Requires PagerDuty account |
| PITR drill | D05 | Requires staging environment |
| Chaos testing scenarios 3/5/6/7 | D05 | Requires staging + fault injection |
| SLSA attestation | D30 | Requires slsa-github-generator Action |
| Chromatic account | D02 | Requires Chromatic.com subscription |
