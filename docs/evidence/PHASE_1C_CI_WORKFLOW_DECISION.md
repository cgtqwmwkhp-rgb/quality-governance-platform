# Phase 1C: CI Workflow for D0 Rehearsal - Decision to Skip

**Phase**: 1C (Optional CI Workflow for Rehearsal)  
**Date**: 2026-01-05  
**Decision**: **SKIP**  
**Status**: ✅ GATE 1C MET (explicitly skipped with justification)

---

## Context

Phase 1C proposed adding a GitHub Actions workflow to automate the D0 rehearsal script execution in CI. This would involve:
- Running `./scripts/rehearsal_containerized_deploy.sh` in GitHub Actions
- Uploading terminal logs as artifacts
- Providing automated evidence for Gate 1

---

## Decision

**We will NOT add a CI workflow for the D0 rehearsal script.**

The rehearsal script will remain a **manual operational procedure** with clear runbook and evidence template.

---

## Rationale

### 1. Existing CI Coverage is Sufficient

The current CI pipeline already provides comprehensive testing:

| Test Category | Coverage | CI Status |
|---------------|----------|-----------|
| Unit Tests | 98 passing | ✅ Running |
| Integration Tests | 77 passing (with PostgreSQL) | ✅ Running |
| Database Migrations | Tested in integration tests | ✅ Running |
| Health Endpoints | `/healthz` and `/readyz` tested | ✅ Running |
| API Endpoints | RBAC, audit events, error envelopes | ✅ Running |
| Security Scan | Dependency vulnerabilities | ✅ Running |
| Code Quality | Black, isort, flake8, mypy | ✅ Running |

**Conclusion**: The rehearsal script does not add new test coverage beyond what CI already provides.

### 2. Rehearsal Script Purpose is Operational, Not CI

The rehearsal script serves **operational purposes**:

| Purpose | Type | Frequency | Environment |
|---------|------|-----------|-------------|
| Local development testing | Development | Ad-hoc | Developer machine |
| Pre-deployment verification | Operations | Before each deployment | Staging/production |
| Disaster recovery practice | Operations | Quarterly or on-demand | Staging/production |

**Conclusion**: Operational drills are not typically automated in CI. They are manual procedures with evidence capture.

### 3. Risk of Flakiness and Gate Weakening

Adding the rehearsal script to CI introduces risks:

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Docker-in-Docker issues | CI failures | Medium | Use GitHub Actions Docker service |
| Network timing issues | Flaky tests | High | Add retries and timeouts |
| PostgreSQL startup delays | Flaky tests | Medium | Increase wait times |
| Resource constraints | Slow CI | High | Use larger runners (cost) |

**Conclusion**: The risk of flakiness outweighs the benefit. Flaky CI weakens gates and creates maintenance burden.

### 4. Constraint Violation

The guidance explicitly states:

> "Any new CI workflow must be deterministic; otherwise skip."
> "Do not weaken any CI gates."

The rehearsal script involves:
- Multi-container orchestration (PostgreSQL + app)
- Network communication between containers
- Timing-dependent health checks
- External dependencies (Docker daemon)

**Conclusion**: The rehearsal script is not deterministic enough for CI. Adding it would violate the constraint.

### 5. Evidence Capture is Manual by Design

The rehearsal script is designed for **evidence capture**:
- Terminal outputs are saved to files
- Health check responses are recorded
- API test results are documented
- Logs are reviewed manually

**Conclusion**: Manual evidence capture is more reliable and comprehensive than automated CI artifacts.

---

## Alternatives Considered

### Alternative 1: Add Rehearsal Script to CI (Rejected)

**Pros**:
- Automated evidence generation
- No manual execution required

**Cons**:
- High risk of flakiness
- Duplicates existing CI tests
- Adds 5-10 minutes to CI time
- Violates "deterministic CI" constraint
- Weakens CI gates

**Decision**: Rejected

### Alternative 2: Add Simplified Rehearsal to CI (Rejected)

**Pros**:
- Reduced complexity (e.g., only health checks)
- Lower risk of flakiness

**Cons**:
- Does not provide full rehearsal evidence
- Still duplicates existing integration tests
- Does not meet Gate 1 requirements (full rehearsal + reset drill)

**Decision**: Rejected

### Alternative 3: Keep Rehearsal as Manual Procedure (Accepted)

**Pros**:
- No CI flakiness risk
- No gate weakening
- Clear operational procedure
- Comprehensive evidence capture
- Aligns with best practices for operational drills

**Cons**:
- Requires manual execution
- Requires Docker-enabled host

**Decision**: Accepted

---

## Implementation

**What We Did Instead**:
1. ✅ Created comprehensive evidence template (`STAGE_D0_REHEARSAL_EXECUTION_ADDENDUM.md`)
2. ✅ Created step-by-step runbook (`D0_REHEARSAL_RUNBOOK.md`)
3. ✅ Created evidence requirements checklist (`GATE_1_EVIDENCE_REQUIREMENTS.md`)
4. ✅ Documented Gate 1 limitation in completion summary
5. ✅ Provided clear action request for repository owner

**What We Did NOT Do**:
- ❌ Add `.github/workflows/d0-rehearsal.yml`
- ❌ Add Docker-in-Docker to CI
- ❌ Duplicate existing integration tests

---

## Precedents and Best Practices

### Industry Precedents

1. **Disaster Recovery Drills**: Not automated in CI
   - Example: AWS Disaster Recovery drills are manual procedures with evidence capture
   - Rationale: Drills test operational procedures, not code correctness

2. **Deployment Rehearsals**: Not automated in CI
   - Example: Kubernetes deployment rehearsals are manual procedures
   - Rationale: Rehearsals test deployment procedures, not application functionality

3. **Operational Runbooks**: Not automated in CI
   - Example: Incident response runbooks are manual procedures
   - Rationale: Runbooks guide human operators, not automated systems

### Best Practices

1. **Separate CI from Operational Procedures**:
   - CI tests code correctness (unit tests, integration tests)
   - Operational procedures test deployment and recovery processes

2. **Avoid Flaky CI**:
   - CI should be deterministic and fast
   - Flaky CI erodes trust and slows development

3. **Evidence-Based Operations**:
   - Operational procedures require evidence capture
   - Manual evidence capture is more reliable than automated artifacts

---

## Consequences

### Positive

1. **No CI Flakiness**: CI remains fast, deterministic, and reliable
2. **No Gate Weakening**: CI gates remain strong and trustworthy
3. **Clear Operational Procedures**: Runbook and evidence template provide clear guidance
4. **Comprehensive Evidence**: Manual evidence capture is more thorough than automated artifacts

### Negative

1. **Manual Execution Required**: Repository owner must execute scripts on Docker-enabled host
2. **Gate 1 Pending**: Cannot proceed to Azure deployment until evidence is committed

### Mitigation

1. **Clear Runbook**: Step-by-step guide makes manual execution straightforward
2. **Evidence Template**: Pre-filled template makes evidence capture easy
3. **Time Estimate**: 15-20 minutes total (reasonable for operational procedure)

---

## Gate 1C Status

**Gate 1C**: ✅ MET

**Justification**: Phase 1C is optional ("only if reliable"). We have explicitly decided to skip this phase with clear justification:
- Rehearsal script is not deterministic enough for CI
- Existing CI coverage is sufficient
- Manual operational procedure is more appropriate
- No gate weakening

**Next Steps**: Proceed to Phase 2A (Azure prerequisites checklist)

---

## Approval

**Proposed By**: Platform Team  
**Reviewed By**: [Pending]  
**Approved By**: [Pending]  
**Date**: 2026-01-05

---

## References

- **Guidance Prompt**: "Optional: add CI artifact export of image digest and staging endpoint smoke results."
- **Constraint**: "Any new CI workflow must be deterministic; otherwise skip."
- **Constraint**: "Do not weaken any CI gates."
- **Best Practice**: Disaster recovery drills are manual procedures, not CI automation

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-05  
**Maintained By**: Platform Team
