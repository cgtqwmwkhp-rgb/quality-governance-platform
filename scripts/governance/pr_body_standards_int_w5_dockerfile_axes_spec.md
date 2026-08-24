# Change Ledger (CL-STANDARDS-INT-W5-DOCKERFILE-AXES-SPEC)

> **Start gate:** Int-W5 #1738 merged @ `9699e5b7a76b`. Staging migration failed; this is the tip hotfix (`STACK_MAX=1`). Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Ship `specs/standards/requirement-axes-v1.json` in the production image.
- **User goal:** Unblock Int-W5 deploy. Staging alembic failed with `FileNotFoundError: /app/specs/standards/requirement-axes-v1.json`; production deploy then failed and started auto-rollback.
- **In scope:** One Dockerfile `COPY` plus a unit pin that the image lists this spec (same class of defect as the compliance-schedule catalogue COPY).
- **Out of scope:** Int-W6 edges; changing TrapGuard; loosening tests; a full image+alembic CI job (noted as follow-up).
- **Feature flag / kill switch:** None. Revert this PR restores the broken deploy.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-W5-HF-01 | Dockerfile | Axes JSON not in image | Copied to `/app/specs/standards/requirement-axes-v1.json` |
| SG-W5-HF-02 | Unit pin | Library specs only | Also asserts W5 axes spec COPY + file exists |

## 3) Compatibility & Data Safety
- Additive image file only. No schema change. Int-W5 migration `20261112_standards_w5_axes` can now run inside ACI.
- **Tolerant reader / strict writer applied?** N/A.
- **Breaking changes:** None.
- **Migration plan:** Next staging deploy applies `20261112_standards_w5_axes` (insert-only). Idempotent by catalogue_key.
- **Rollback strategy (DB):** No DB change in this PR. Reverting restores the missing-file failure.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Deploy migration honesty | CI green, staging FileNotFound | Image contains the file migrations actually read |
| ≥98% + EXACT | Unchanged | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Dockerfile copies `specs/standards/requirement-axes-v1.json` to the path the failing deploy named.
- [x] AC-02: Unit test fails if that COPY line is removed.
- [x] AC-03: No other image path / ownership pattern changes.
- [ ] AC-04: Staging `Run database migrations` succeeds; STG health SHA = PROD health SHA = this tip.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_dockerfile_library_specs.py`
- [ ] Hosted CI — pending PR checks
- Failing evidence: Azure Staging run 31641009374 (`FileNotFoundError` on axes JSON)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Deploy migration can open `/app/specs/standards/requirement-axes-v1.json` instead of aborting.
- [x] CUJ-02: Existing spec COPY lines (taxonomy / functions / compliance catalogue) remain.

## 7) Observability & Ops
- Staging run 31641009374 is the SoR for this failure class.
- Health SHA matching the merge commit is **not** sufficient while this migration has not applied.
- Follow-up: CI still does not build the image and run `alembic upgrade head` inside it.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after CI green (`STACK_MAX=1`).
2. Staging: migration step past `20261112_standards_w5_axes`.
3. Production: health SHA = tip; only then mark Int-W5 LIVE / DONE.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Staging migration fails for a *new* missing file after this COPY.
- **Rollback steps:** Do not revert this COPY. Read the new FileNotFound path and add that COPY. If the pipeline must be cleared, revert #1738 so the W5 migration leaves the chain.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Failed staging: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/31641009374
- Parent merge: PR #1738 @ `9699e5b7a76b`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc)
- [x] **Gate 1:** Dockerfile + unit pin
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG migration success + health tip
- [ ] **Gate 4:** PROD health = tip
- [ ] **Gate 5:** Master conveyor Int-W5 LIVE
