# Security Review Log (D06)

Tracking log for internal security reviews of the Quality Governance Platform.

## Review Template

| Field | Value |
|-------|-------|
| **Review Date** | YYYY-MM-DD |
| **Reviewer** | Name / Team |
| **Scope** | Module or feature reviewed |
| **Findings** | Summary of findings (count by severity) |
| **Actions** | Remediation items created |
| **Status** | Open / Closed |

## Reviews Conducted

| # | Date | Scope | Reviewer | Critical | High | Medium | Low | Status |
|---|------|-------|----------|----------|------|--------|-----|--------|
| 1 | 2026-03-20 | CI security pipeline | Platform Eng | 0 | 0 | 2 | 3 | Closed |

## CI Security Gates

| Gate | Tool | Status |
|------|------|--------|
| Dependency audit (Python) | `pip-audit` | Active |
| Dependency audit (npm) | `npm audit` | Active |
| Secret scanning | `gitleaks` | Active |
| SBOM generation | `cyclonedx` | Active |
| Security covenant | `ci-security-covenant` | Active |

## Related Documents

- [`docs/security/pentest-plan.md`](../security/pentest-plan.md) — external pentest plan
- [`docs/security/threat-model.md`](../security/threat-model.md) — STRIDE-based threat model
