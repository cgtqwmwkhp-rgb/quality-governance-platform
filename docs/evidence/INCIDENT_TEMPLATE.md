# Incident Template

## Incident ID Format

```
INC-YYYY-MM-DD-{ENVIRONMENT}-{TYPE}
```

Examples:
- `INC-2026-01-30-STAGING-UNAVAILABLE`
- `INC-2026-01-30-STAGING-FAILED`
- `INC-2026-01-30-PRODUCTION-DEGRADED`

## Incident Types

| Type | Description | Severity |
|------|-------------|----------|
| `UNAVAILABLE` | Environment not reachable or container app not deployed | P1 - Critical |
| `FAILED` | Environment reachable but contract checks failed | P2 - High |
| `DEGRADED` | Critical checks pass, non-critical failed | P3 - Medium |

## Incident Report Template

```markdown
# Incident Report: INC-YYYY-MM-DD-ENV-TYPE

## Summary
- **Incident ID**: INC-YYYY-MM-DD-ENV-TYPE
- **Environment**: staging / production
- **Detected By**: nightly-contract-verification / post-deploy-probe
- **Detection Time**: YYYY-MM-DD HH:MM:SS UTC
- **Resolved Time**: (TBD)
- **Duration**: (TBD)

## Impact
- [ ] API endpoints unavailable
- [ ] Contract checks failing
- [ ] Data processing blocked

## Timeline
| Time (UTC) | Event |
|------------|-------|
| HH:MM | Issue detected by automated probe |
| HH:MM | On-call notified |
| HH:MM | Investigation started |
| HH:MM | Root cause identified |
| HH:MM | Fix deployed |
| HH:MM | Issue resolved |

## Root Cause
(Description of what caused the incident)

## Resolution
(Description of how the issue was resolved)

## Prevention
(Actions to prevent recurrence)

## Evidence
- Workflow Run: https://github.com/org/repo/actions/runs/{run_id}
- Probe Artifact: etl-contract-probe-{run_id}
- Logs: (link to relevant logs)
```

## Escalation Path

1. **P1 - Critical** (UNAVAILABLE): Immediate on-call notification
2. **P2 - High** (FAILED): Notify within 1 hour
3. **P3 - Medium** (DEGRADED): Notify within 4 hours

## Related Documentation

- [ADR-0004: ACA Staging Infrastructure](../adr/ADR-0004-ACA-STAGING-INFRASTRUCTURE.md)
- [Environment Endpoints](environment_endpoints.json)
- [ETL Contract Probe](../../scripts/etl/contract_probe.py)
