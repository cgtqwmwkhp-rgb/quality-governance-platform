# Operational Runbooks

This directory contains operational procedures for deploying, managing, and troubleshooting the Quality Governance Platform.

## Available Runbooks

### [DATABASE_MIGRATIONS.md](./DATABASE_MIGRATIONS.md)
Database schema change procedures using Alembic. Covers migration workflow, backup procedures, rollback strategies, and troubleshooting.

**Use when**: Applying database schema changes, upgrading database versions, or recovering from failed migrations.

---

### [APPLICATION_LIFECYCLE.md](./APPLICATION_LIFECYCLE.md)
Application startup, shutdown, and restart procedures. Covers health checks, configuration reload, and troubleshooting.

**Use when**: Starting/stopping the application, performing maintenance, or diagnosing runtime issues.

---

### [ROLLBACK_PROCEDURES.md](./ROLLBACK_PROCEDURES.md)
Emergency rollback procedures for failed deployments. Covers database rollback, application rollback, and configuration rollback.

**Use when**: A deployment has failed and you need to quickly restore the previous working state.

---

### [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)
Comprehensive pre-deployment and post-deployment verification checklists. Ensures all steps are completed safely.

**Use when**: Planning and executing any deployment to production or staging environments.

---

## Quick Reference

### Health Checks
```bash
# Liveness check
curl http://localhost:8000/healthz

# Readiness check (includes database)
curl http://localhost:8000/readyz
```

### Common Operations
```bash
# Check migration status
alembic current

# Start application
systemctl start quality-governance-platform

# Check logs
tail -f /var/log/quality-governance-platform/app.log
```

---

## Runbook Maintenance

These runbooks should be reviewed and updated:
- After each deployment that introduces new procedures
- When operational issues reveal gaps in documentation
- Quarterly as part of operational review
- When infrastructure or tooling changes

---

## Emergency Contacts

For production incidents:
- **On-Call Engineer**: [Contact Info]
- **Database Team**: [Contact Info]
- **Escalation**: [Contact Info]

---

## Related Documentation

- [ADR-0001: Migration Discipline](../adrs/ADR-0001-migration-discipline-and-ci-strategy.md)
- [ADR-0002: Fail-Fast Testing](../adrs/ADR-0002-fail-fast-testing-strategy.md)
- [Stage 1.0 Evidence](../evidence/)
