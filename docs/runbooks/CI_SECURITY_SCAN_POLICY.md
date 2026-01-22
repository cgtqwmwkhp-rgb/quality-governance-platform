# CI Security Scan Policy

**Version:** 1.0  
**Date:** 2026-01-22  
**Owner:** Platform Security Team

## Overview

This document defines when and why security scans run in the CI pipeline, including explanations for jobs that may appear as "skipping" in certain contexts.

## Security Scan Matrix

| Scan | Trigger | Scope | Blocking? |
|------|---------|-------|-----------|
| **Dependency Vulnerability (Safety)** | All pushes + PRs | Python dependencies | No (report only) |
| **Code Security (Bandit)** | All pushes + PRs | Python source code | Yes (High severity) |
| **Security Tests** | All pushes + PRs | Custom security tests | No (report only) |
| **Secret Detection (Gitleaks)** | All pushes + PRs | Git history | No (report only) |
| **CodeQL Analysis** | All pushes + PRs | Python + JavaScript | No (report only) |
| **Container Security (Trivy)** | Main branch only | Docker image | No (report only) |
| **pip-audit** | All pushes + PRs | Python dependencies | Yes (blocking) |

## Container Security Scan - Why It May Skip

### Condition
```yaml
container-scan:
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
```

### When It Runs
- ✅ Direct push to `main` branch
- ✅ Merge commit to `main` branch
- ✅ Weekly scheduled scan (Sundays 2am UTC)

### When It Skips
- ⏭️ Pull requests (all branches)
- ⏭️ Pushes to non-main branches (develop, feature/*)

### Why Skipping on PRs is Safe

1. **Build Cost:** Docker image build adds ~2-3 minutes to every CI run
2. **Scan Triggers on Merge:** The scan WILL run when PR is merged to main
3. **Redundant Coverage:** Dependency scans (Safety, pip-audit) cover Python deps
4. **CodeQL Runs on PRs:** Static analysis catches code issues before merge
5. **Weekly Schedule:** Catches new CVEs even without code changes

### Verification

To verify Container Security Scan runs on main:

```bash
# Check recent runs on main branch
gh run list --workflow=security-scan.yml --branch=main --limit=10
```

Expected: "Container Security Scan" shows as "pass" or "fail", not "skipping"

## Alternative Scans on PRs

When Container Security Scan skips on a PR, these scans still run:

| Scan | Covers |
|------|--------|
| pip-audit | Python dependency vulnerabilities |
| Safety | Python dependency vulnerabilities (JSON report) |
| Bandit | Code security issues (SQL injection, etc.) |
| CodeQL | Static analysis (Python + JavaScript) |
| Gitleaks | Secrets in code |

## Escalation

If a container vulnerability is discovered:

1. Review Trivy SARIF report in GitHub Security tab
2. Update base image or dependency
3. Re-run security scan workflow manually if needed:
   ```bash
   gh workflow run security-scan.yml
   ```

## Audit Trail

All security scan results are:
- Uploaded as GitHub artifacts (30-day retention)
- Published to GitHub Security tab (SARIF format)
- Logged in workflow run history

## Policy Changes

Any changes to security scan conditions must:
1. Be documented in this file
2. Be reviewed by security team
3. Maintain coverage for main branch
4. Not reduce blocking gates
