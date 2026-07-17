# Change Ledger (CL-CD-MANUAL-DISPATCH-TIP-SHA)

## 1) Summary
- **Feature / Change name:** CD-MANUAL-DISPATCH-TIP-SHA — manual prod dispatch promotes dispatch ref, not stale signoff SHA
- **User goal:** `workflow_dispatch` with `staging_verified=true` and empty `release_sha` deploys the checked-out main tip (when it descends from signed release), matching auto-promote after staging
- **In scope:** `.github/workflows/deploy-production.yml` validate step only
- **Out of scope:** Alembic, release_signoff.json update, prod deploy trigger
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend / APIs / DB:** None
- **CI/CD:** Pre-deployment `release_sha` selection for manual dispatch
- **Config/env/flags:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Aligns manual dispatch with existing `workflow_run` descendant-of-signed gate
- **Breaking changes:** None — explicit `release_sha` input unchanged; mismatched SHAs still blocked
- **Migration plan:** N/A
- **Rollback strategy:** Revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Empty `release_sha` on manual dispatch defaults to `${{ github.sha }}`, not `release_signoff.json` SHA
- [x] AC-02: Dispatch SHA must equal or descend from signed SHA (same rule as auto-promote)
- [x] AC-03: Explicit `release_sha` input still honoured

## 5) Testing Evidence
- [x] Root-cause verified on run 29606506913: pinned `640a163a` → migration `Can't locate revision 20260723_rr_notes_act`
- [ ] CI workflow lint after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Manual force_deploy from main tip selects `15eab9f8` (not `640a163a`) when signoff is ancestor

## 7) Observability & Ops
- Pre-deployment summary already logs Signed Release SHA vs selected release_sha

## 8) Release Plan
- Merge to main; no prod deploy from this PR alone
- Immediate unblock (no merge required): dispatch with explicit `release_sha=15eab9f8…`

## 9) Rollback Plan
- **Rollback trigger:** Manual prod deploy selects wrong SHA
- **Rollback steps:** Revert squash-merge
- **Owner:** Platform / CD

## 10) Evidence Pack
- Failed run: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/29606506913
- Prod API: `build_sha=640a163a` vs main tip `15eab9f8`
- Signoff: `docs/evidence/release_signoff.json` → `640a163a` (2026-07-11)

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [ ] **Gate 1:** CI green
- [ ] **Gate 2:** Merge after review (does not auto-deploy prod)
