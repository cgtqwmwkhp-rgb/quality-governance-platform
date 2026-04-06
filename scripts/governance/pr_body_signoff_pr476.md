# Change Ledger (CL-SIGNOFF-BFDB8D20)

## 1) Summary
- **Feature / Change name:** Release sign-off artifact sync for production baseline bfdb8d20
- **User goal (1-2 lines):** Align `docs/evidence/release_signoff.json` with the live promoted commit (PR #476 merge) and CI/staging/production workflow runs.
- **In scope:** `docs/evidence/release_signoff.json` only
- **Out of scope:** Application code, workflows
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend / Backend / APIs / DB / Workflows / Deps:** None
- **Governance artifacts:** `release_signoff.json` — `release_sha` bfdb8d20, `deployment_evidence` run IDs 24048283123 / 24048507361 / 24048754989, live HTTP proof timestamp

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Documentation-only JSON
- **Breaking changes:** None

## 4) Acceptance Criteria (AC)
- [x] AC-01: `release_sha` matches live prod `build_sha` bfdb8d20576ee228b63a7bcde010275eca4b207d (curl 2026-04-06T20:12:02Z)
- [x] AC-02: `validate_release_signoff.py --file docs/evidence/release_signoff.json --sha bfdb8d20576ee228b63a7bcde010275eca4b207d` exits 0
- [x] AC-03: CUJ-01..CUJ-03 labels present

## 5) Testing Evidence (link to runs)
- [x] CI — https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24048283123
- [x] Staging deploy — run 24048507361
- [x] Production deploy — run 24048754989

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Production `GET /api/v1/meta/version` returns `build_sha` bfdb8d20
- [x] CUJ-02: Staging deploy workflow success (HTTP from this agent: DNS failure for staging hostname)
- [x] CUJ-03: Production `/health` and `/readyz` return HTTP 200

## 7) Observability & Ops
- **No change**

## 8) Release Plan
- **Merge sign-off PR to main** — aligns artifact for next production gate; app already live on bfdb8d20

## 9) Rollback Plan
- Revert this PR if sign-off text is wrong; does not roll back running containers

## 10) Evidence Pack
- Prod version JSON captured at merge audit

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Change Ledger complete
- [x] **Gate 1:** N/A — governance JSON only
- [ ] **Gate 2:** CI green on PR
- [ ] **Gate 3:** Staging verification N/A for sign-off-only PR
- [ ] **Gate 4:** Canary N/A
- [x] **Gate 5:** Live prod verified bfdb8d20 (curl) before this governance commit
