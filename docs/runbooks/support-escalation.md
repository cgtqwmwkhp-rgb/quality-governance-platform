# L1/L2 Support Escalation Runbook

**Last updated**: 2026-04-03

## Triage Levels

| Level | Scope | Response SLA | Owner |
|-------|-------|-------------|-------|
| L1 | Known issues, FAQ, password resets | 30 min ack | Support team |
| L2 | Bugs, configuration, data fixes | 4 hours ack | Platform engineers |
| L3 | Architecture, security, data loss | 1 hour ack | Senior engineers |

## Escalation Triggers

### L1 to L2

- User reports a bug not covered by known issues list
- Error persists after standard troubleshooting steps
- Data inconsistency reported by user
- Performance degradation noticed by multiple users

### L2 to L3

- Production outage affecting >10% of users
- Security incident or suspected breach
- Data integrity issue affecting auditable records
- Failed automated rollback

## Diagnostic Steps (L1)

1. Check platform health: `python scripts/admin_cli.py health`
2. Check database status: `python scripts/admin_cli.py db-status`
3. Check feature flags: `python scripts/admin_cli.py feature-flags`
4. Check pool status: `python scripts/admin_cli.py pool-status`
5. Review KQL queries in `docs/ops/kql-queries.md` for common patterns

## Communication Template

```
Subject: [L{LEVEL}] {Brief description}
Priority: {Critical|High|Medium|Low}
Impact: {Number of users affected}
Timeline: {When issue started}
Current status: {Investigating|Mitigating|Resolved}
Next update: {ETA}
```

## On-Call Rotation

- Primary: Platform engineer on-call (see team calendar)
- Secondary: Engineering manager
- Emergency: CTO direct line

## Post-Incident

1. Create incident record in QGP
2. Conduct blameless post-mortem within 48 hours
3. Document in `docs/runbooks/` if new failure mode
4. Update known issues list
