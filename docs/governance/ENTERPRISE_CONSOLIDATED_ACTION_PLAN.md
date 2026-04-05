# Enterprise Consolidated Action Plan

**Program:** Quality Governance Platform (QGP)  
**Document type:** Cross-release rollup (governance + engineering + security + QA)  
**Baseline `origin/main`:** `054658e6bdf2b3210738cdf65198ddc97d1233be` (includes merged **PR #444**)  
**Document version:** 1.1  
**Last updated:** 2026-04-05  
**Classification:** Internal — release governance

---

## 1. Purpose

This plan **rolls up** outcomes, residual risks, and opportunities from **approximately the last twenty-eight merged pull requests** on `main` (roughly **#415–#444**, with emphasis **#417–#444**), plus **documented gap programs** (`GAP-001–003`, WCS blueprint, best-in-class gap analysis), and **recent pre-production audit themes** (contract alignment, container scanning, coverage policy, i18n, readiness probes).

It is intended for **Fortune 500-style operating discipline**: traceability, staged delivery, explicit gates, rollback, and evidence packs—not a flat backlog list.

---

## 2. Source evidence (no invented scope)

| Source | Path or pointer |
|--------|------------------|
| Merged PR history | GitHub `main` merge log; representative titles in §4 |
| GAP remediation (delivered + backlog) | `docs/governance/GAP-001-003-remediation-plan.md` |
| Strategic gap catalog | `docs/GAP_ANALYSIS_BEST_IN_CLASS.md` |
| Coverage gate reconciliation | `docs/evidence/test-coverage-baseline.md`, `pyproject.toml` |
| Security automation | `.github/workflows/security-scan.yml` |
| Release sign-off discipline | `docs/evidence/release_signoff.json` |
| Diagnostics / readiness | `docs/ops/diagnostics-endpoint-guide.md` |
| i18n posture | `docs/i18n/locale-coverage.md` |
| OpenAPI SSOT | `docs/contracts/openapi.json` (path count via tooling, not hand-waved) |

---

## 3. Document revision process (two passes)

### Revision 1 — Consolidation draft

**Objective:** Aggregate threads into a single inventory.

**R1 outputs (internal criteria):**

- Thematic grouping of merged PRs (governance hardening, contracts, risk/CAPA, evidence/signoff, ops URLs).
- Deduplication of “optional follow-ups” vs **closed** work.
- Explicit labeling of **residual** CI failures (e.g. parallel Security Scan) vs **merge-blocking** CI.

### Revision 2 — Fortune 500 operating model (this document)

**R2 enhancements over R1:**

| Dimension | R1 | R2 |
|-----------|----|----|
| **Sequencing** | Thematic list | **Waves** with dependencies and merge-safety |
| **Ownership** | Implied | **RACI** per wave |
| **Quality bars** | Mentioned | Mapped to **Gates A–F** and existing Change Ledger |
| **Risk** | Narrative | **Residual risk register** with severity and evidence |
| **Opportunities** | Mixed with defects | Separate **opportunity register** (value / cost / risk) |
| **Traceability** | PR titles | **PR → outcome → residual** matrix |

### Revision 2.1 — Second editorial pass (errors / issues / options unification)

**Objective:** Map informal language (“errors”, “issues”, “options”) to **one** program vocabulary so CAB and engineering share definitions.

| Informal term | Maps to in this plan |
|---------------|----------------------|
| **Errors** | CI/workflow **failures** with logs (e.g. Security Scan / Trivy) → **RIR-001** |
| **Issues** | Product/engineering **defects or debt** → **RIR-002–RIR-010** |
| **Options** | **Decision forks** (Redis on/off, Trivy waiver vs fix, coverage interpretation) → Wave notes + CAB minutes |
| **Opportunities** | Strategic **enhancements** → **OPP-001–OPP-007** |

**Additions:** §13 rollup table; §14 automation + CLI evidence standard.

### Revision 2.2 — Third editorial pass (KPIs + production clarity)

**Objective:** Fortune 500 **scorecard** hygiene and explicit **docs-only vs application promotion** behaviour.

- **KPI scorecard** → §15 (review cadence targets; not numeric SLAs unless ops adopts).  
- **Production clarity:** Merging **documentation-only** commits updates `origin/main` and may trigger deploy workflows, but **`GET /api/v1/meta/version` `build_sha`** only advances when a **new application image** is built and promoted—track both **git SHA** and **`build_sha`** in signoff packs.

---

## 4. Merged PR rollup (recent window)

*Deterministic ordering: ascending PR number. Titles from merge history; verify in GitHub if disputed.*

| PR | Theme | Outcome (summary) |
|----|-------|-------------------|
| #417 | Governance / mypy / CD | Debt closure, CD behaviour aligned with signed descendants |
| #418 | Evidence | Signoff aligned with #417 production |
| #419 | CD | Auto-production when staging descends from signed `release_sha` |
| #420 | Evidence | Predator v4 completion evidence |
| #421 | Evidence | Production deploy evidence |
| #422 | Evidence | Production evidence #421 |
| #423 | A11y | Radix `DialogDescription` test compliance |
| #424 | Evidence | Signoff #423 |
| #425 | Ops | SWA hostname SSOT vs Azure defaults |
| #426 | Evidence | Coverage baseline doc ↔ CI thresholds |
| #427 | Evidence | Production 295c74ac |
| #428 | Hardening | NearMiss / mypy / scorecard |
| #429 | Evidence | Signoff #428 |
| #430 | Governance | Quarantine lift, compliance APIs, CI seeds, ZAP rules |
| #431 | Audits | ISO import presets / scheme canonicalisation |
| #433 | GAP slice | GAP-001–003 features (triage, cross-standard UX, glossary) |
| #434 | Evidence | GAP production SHA update |
| #435 | Risk | Reject triage + optional notes |
| #436 | Governance | CAPA bridge, toasts, pillar docs |
| #437 | Evidence | Signoff #436 |
| #439 | Contracts | OpenAPI sync + triage integration tests |
| #440 | Evidence | Signoff #439 |
| #441 | Frontend | Risk-register client OpenAPI alignment (bowtie + KRI) |
| #442 | Evidence | Signoff #441 |
| #443 | Evidence | Production `httpsOnly` note |
| #444 | Governance | Enterprise consolidated action plan (this document; PR rollup + R1/R2 structure) |

**Cross-cutting wins already in production narrative:** contract SSOT movement, smoke/E2E stabilisation threads, portal stats routing, governance hand-off UX, import risk triage, release evidence hygiene, Azure https-only hardening (per signoff notes).

---

## 5. Residual issue & error register

*Stable IDs for program tracking. Severity: P0 release blocker / P1 major / P2 medium / P3 minor.*

| ID | Severity | Class | Symptom | Evidence | Wave |
|----|----------|-------|---------|----------|------|
| **RIR-001** | P1 | SECURITY / CI | `Container Security Scan` (Trivy) can fail on `main` pushes | `.github/workflows/security-scan.yml` (`exit-code: '1'`, HIGH/CRITICAL); `release_signoff.json` `pre_existing_failures` | W1 |
| **RIR-002** | P2 | RELIABILITY | Redis may show `not_configured` in readiness if `REDIS_URL` unset | `docs/ops/diagnostics-endpoint-guide.md` | W2 |
| **RIR-003** | P2 | QA / GOVERNANCE | Dual coverage story: CI job floors vs combined `fail_under` | `docs/evidence/test-coverage-baseline.md`, `pyproject.toml` | W2 |
| **RIR-004** | P2 | DX | Mypy override groups remain for several routes/services | `pyproject.toml` `[[tool.mypy.overrides]]` | W3 |
| **RIR-005** | P3 | DX | Python `type: ignore` ratchet ceiling | `scripts/validate_type_ignores.py` `MAX_TYPE_IGNORES` | W3 |
| **RIR-006** | P2 | UX / FE | Bow-tie view still uses illustrative static cause labels | `frontend/src/pages/RiskRegister.tsx` (mapped causes array) | W2 |
| **RIR-007** | P2 | I18N | Welsh (`cy`) partial coverage | `docs/i18n/locale-coverage.md` | W4 |
| **RIR-008** | P3 | CI | DAST / ZAP baseline advisory (non-blocking per hygiene docs) | `release_signoff.json` | W4 |
| **RIR-009** | P2 | GOVERNANCE | OpenAPI path count large; FE↔contract matrix not automated | `docs/contracts/openapi.json`; audit methodology gap | W2 |
| **RIR-010** | P3 | OPS | `main` SHA may advance beyond last signed production `release_sha` | Normal promotion lag; track via signoff | W0 |

---

## 6. Opportunity register (enhancement, not defects)

*From `GAP_ANALYSIS_BEST_IN_CLASS.md` and GAP Pillar III backlog—**strategic**, not committed delivery.*

| ID | Opportunity | Value | Cost (indicative) | Dependencies |
|----|-------------|-------|-------------------|--------------|
| **OPP-001** | SIF / pSIF classification & controls | Regulatory + exec reporting | L | Safety science SME |
| **OPP-002** | Offline-first portal queue | Field reliability | M–L | Sync conflict model |
| **OPP-003** | Incident cost + LTI metrics | Finance + TRIF alignment | M | HR / finance data |
| **OPP-004** | Analytics depth (heatmaps, geo time-series) | P3 persona satisfaction | M | Data warehouse |
| **OPP-005** | Workflow automation expansion | P4 admin efficiency | L | BPMN / rules engine |
| **OPP-006** | Auto `ComplianceEvidenceLink` on promote | GAP-001 depth | M | Job + idempotency |
| **OPP-007** | UVDB / Planet Mark matrix seed data | GAP-001 depth | M | Content governance |

---

## 7. Execution waves (ordered, PR-safe)

### Wave 0 — Operating cadence (continuous)

| Action | DoD | Owner |
|--------|-----|-------|
| Keep `release_signoff.json` aligned with promoted SHA | Signoff + live `GET /api/v1/meta/version` match | Release manager |
| Monitor parallel Security Scan vs merge-blocking CI | Weekly triage notes | Sec + Platform |
| Staging before prod promotion | Existing deploy workflows green | DevOps |

### Wave 1 — Security debt (Trivy)

- **Objective:** Clear **RIR-001** or obtain formal waiver with compensating controls documented in CAB pack.
- **Approach:** Base image pin, OS package updates, rebuild, re-scan; avoid silent `.trivyignore` without Sec review.
- **Tests:** `security-scan` workflow green on `main`; smoke deploy unchanged.
- **Rollback:** Revert Dockerfile / image tag; restore last known-good digest.

### Wave 2 — Reliability & contract hygiene

- **RIR-002:** Decide prod Redis requirement; configure `REDIS_URL` + Key Vault reference if **yes**.
- **RIR-006:** Replace static bow-tie causes with API-driven elements (feature-flag if schema unstable).
- **RIR-009:** Add generated report: OpenAPI operations × TS client calls (CI advisory → blocking when stable).

### Wave 3 — Type system & maintainability

- **RIR-004 / RIR-005:** Burn down mypy overrides and ratchet `type: ignore` count with module-level tests.

### Wave 4 — Quality bar & i18n

- **RIR-003:** Publish single “authoritative” coverage interpretation for CAB; optionally align jobs.
- **RIR-007:** Execute phased `cy` milestones from locale coverage doc.
- **RIR-008:** Revisit ZAP promotion criteria per `docs/compliance/ci-gate-hygiene.md`.

---

## 8. RACI (summary)

| Wave | Responsible | Accountable | Consulted | Informed |
|------|-------------|-------------|-----------|----------|
| W0 Release hygiene | Platform Eng | Release manager | Security | Product |
| W1 Trivy | Sec + Backend | CISO delegate | DevOps | Product |
| W2 Redis / contracts / bow-tie | Backend + FE | Engineering lead | QA | Support |
| W3 Typing | Backend | Tech lead | QA | All devs |
| W4 Coverage / i18n / DAST | QA + FE | Quality lead | Legal (i18n) | Product |

---

## 9. Release gate mapping

Maps to `scripts/governance/pr_body_template.md` and enterprise **Gates A–F**:

| Gate | Enforced by | Wave relevance |
|------|-------------|----------------|
| A — Static (lint, type, format) | CI + `make pr-ready` | All |
| B — Unit / integration | CI pytest jobs | W2–W4 |
| C — E2E smoke | Playwright / smoke jobs | W2+ |
| D — Canary + SLO | Azure + `docs/slo/*` | Production promotion |
| E — UAT sign-off | `release_signoff.json` | Each production cut |
| F — Post-deploy verification | `/healthz`, `/readyz`, `/api/v1/meta/version` | Each production cut |

---

## 10. Traceability — PR outcomes to residual risk

| PR band | Primary residual risks |
|---------|-------------------------|
| #417–#430 | CI/security parallel failures (Trivy); ongoing typing debt |
| #431–#437 | GAP deeper automation (Pillar III backlog); i18n phases |
| #439–#441 | Contract drift without generator; bow-tie UX completeness |
| #442–#444 | #442–#443: operational discipline (evidence). **#444:** program backbone doc; no runtime defect implied |

---

## 13. Single rollup — errors, issues, options, opportunities

*Deterministic ordering: by register ID.*

| Bucket | ID | Title | Disposition |
|--------|-----|-------|-------------|
| **Error (CI)** | RIR-001 | Trivy / Security Scan can fail on `main` | **W1** — remediate or governed waiver |
| **Issue** | RIR-002 | Redis `not_configured` in `/readyz` | **W2** — product decision + Azure `REDIS_URL` if required |
| **Issue** | RIR-003 | Dual coverage enforcement story | **W4** — CAB-authoritative interpretation |
| **Issue** | RIR-004 | Mypy overrides | **W3** — burn-down |
| **Issue** | RIR-005 | `type: ignore` ratchet | **W3** — burn-down |
| **Issue** | RIR-006 | Bow-tie static UX | **W2** — API-backed UI |
| **Issue** | RIR-007 | Partial Welsh locale | **W4** — phased `cy` |
| **Issue** | RIR-008 | ZAP advisory | **W4** — promotion criteria |
| **Issue** | RIR-009 | No automated OpenAPI↔FE matrix | **W2** — CI report |
| **Issue** | RIR-010 | `main` ahead of signed app `release_sha` | **W0** — normal; signoff on app promote |
| **Opportunity** | OPP-001–007 | Strategic enhancements | Quarterly portfolio review |
| **Option** | OPT-A | **Redis:** required vs optional in prod | Architecture + SRE; document in runtime inventory |
| **Option** | OPT-B | **Trivy:** fix vs time-bound waiver | Security + CAB |
| **Option** | OPT-C | **Coverage:** single published “gate of record” | QA lead + chapter in `test-coverage-baseline.md` |

---

## 14. Automation, evidence tooling, and “standard” CLI usage

**Should Azure CLI and GitHub CLI be standard?** For **release evidence**, **yes** as the default toolchain: they produce reproducible artefacts (App Service state, workflow run IDs) already referenced in `docs/evidence/release_signoff.json`. Formal **policy** (“must use az/gh for signoff”) belongs in CAB / platform standards outside this file; this plan **recommends** adoption.

| Automation target | Purpose | Suggested owner | Wave |
|-------------------|---------|-----------------|------|
| OpenAPI × TS client coverage report | **RIR-009** | Platform Eng | W2 |
| Weekly Security Scan triage export | **RIR-001** | Security | W0 |
| `readyz` JSON in post-deploy script | **RIR-002** visibility | DevOps | W0 |
| Locale coverage trend | **RIR-007** | FE + Content | W4 |

---

## 15. KPI scorecard (review targets)

*Targets are **governance review triggers**, not deployed metrics unless wired to observability.*

| KPI | Measurement | Review frequency | Healthy signal |
|-----|-------------|------------------|----------------|
| **Merge-blocking CI** | GitHub required checks on `main` | Every merge | Green |
| **Security Scan (parallel)** | `Security Scan` workflow | Weekly | Green or waiver on file |
| **Prod readiness** | `GET /readyz` | Each deploy | `status: ready`, DB connected |
| **Release integrity** | `build_sha` vs `release_signoff.json` | Each production cut | Match for **app** releases |
| **Contract drift** | OpenAPI vs client report | Monthly | Zero unapproved drift |
| **Typing debt** | Mypy override count / `MAX_TYPE_IGNORES` | Quarterly | Downward trend |

---

## 16. Definition of program success

1. **Production** remains **Running** with **httpsOnly** and verifiable **`build_sha`** for **application** releases (Azure + `GET /api/v1/meta/version`).  
2. **Merge-blocking CI** stays green; **Security Scan** either green or **explicitly governed** waivers for Trivy.  
3. **No silent FE/BE contract drift**—generator or contract tests in CI.  
4. **CUJ smoke** evidence attached to each production **application** signoff.  
5. **Opportunity register** reviewed quarterly; waves re-prioritised by risk and value.  
6. **`origin/main` git SHA** may advance on **docs-only** merges without changing **`build_sha`** until the next backend/frontend artefact promotion—both SHAs recorded where relevant.

---

## 17. Maintenance

- **Owner:** Platform / Quality governance (rotating).  
- **Review cadence:** Monthly rollup diff against `main` merge log; quarterly opportunity refresh.  
- **Supersedes:** Informal chat summaries; does **not** replace per-PR Change Ledgers.
