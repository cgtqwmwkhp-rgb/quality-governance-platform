# Deployment Checklist

**Purpose**: Comprehensive pre-deployment and post-deployment verification  
**Audience**: Release Engineers, DevOps, SRE  
**Last Updated**: 2026-01-04

---

## Pre-Deployment Checklist

### Planning
- [ ] Deployment scheduled and stakeholders notified
- [ ] Maintenance window reserved (if downtime required)
- [ ] Rollback plan documented
- [ ] On-call engineer identified

### Code Review
- [ ] All PRs reviewed and approved
- [ ] CI/CD pipeline passing (all gates green)
- [ ] No critical security vulnerabilities
- [ ] Code coverage maintained or improved

### Testing
- [ ] Unit tests passing (100%)
- [ ] Integration tests passing (100%)
- [ ] Staging environment tested
- [ ] Performance testing completed (if applicable)
- [ ] Security scan passed

### Database
- [ ] Database backup completed and verified
- [ ] Migration tested in staging
- [ ] Migration SQL reviewed
- [ ] Rollback migration tested

### Configuration
- [ ] Environment variables reviewed
- [ ] Secrets rotated (if required)
- [ ] Configuration changes documented
- [ ] `.env.example` updated

### Documentation
- [ ] CHANGELOG updated
- [ ] API documentation updated (if applicable)
- [ ] Runbooks updated
- [ ] Known issues documented

---

## Deployment Checklist

### Pre-Deployment
- [ ] Verify CI/CD pipeline status
- [ ] Create database backup
- [ ] Tag release in Git
- [ ] Notify stakeholders of deployment start

### Database Migration
- [ ] Stop application (if required)
- [ ] Apply database migrations
- [ ] Verify migration version
- [ ] Run post-migration validation queries

### Application Deployment
- [ ] Deploy new application version
- [ ] Start application
- [ ] Wait for startup (30s)
- [ ] Verify health checks passing

### Smoke Tests
- [ ] Test `/healthz` endpoint
- [ ] Test `/readyz` endpoint
- [ ] Test critical API endpoints
- [ ] Verify database connectivity
- [ ] Check application logs

---

## Post-Deployment Checklist

### Immediate (0-5 minutes)
- [ ] Health checks passing
- [ ] No ERROR logs
- [ ] Critical functionality working
- [ ] Performance metrics normal

### Short-term (5-30 minutes)
- [ ] Monitor error rates
- [ ] Monitor response times
- [ ] Monitor database query performance
- [ ] Check for memory leaks
- [ ] Verify background jobs running

### Long-term (30+ minutes)
- [ ] Monitor user-reported issues
- [ ] Check system resource usage
- [ ] Verify data integrity
- [ ] Review application metrics

### Finalization
- [ ] Notify stakeholders of successful deployment
- [ ] Update deployment log
- [ ] Close deployment ticket
- [ ] Schedule post-deployment review (if needed)

---

## Rollback Checklist

If deployment fails:

- [ ] Stop deployment immediately
- [ ] Assess impact and severity
- [ ] Decide: fix forward or rollback?
- [ ] Execute rollback procedure (see ROLLBACK_PROCEDURES.md)
- [ ] Verify rollback successful
- [ ] Notify stakeholders
- [ ] Create incident report
- [ ] Schedule post-mortem

---

## Deployment Verification Commands

```bash
# Health checks
curl -f http://localhost:8000/healthz
curl -f http://localhost:8000/readyz

# Check logs
tail -n 100 /var/log/quality-governance-platform/app.log | grep ERROR

# Check process
systemctl status quality-governance-platform

# Check database
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT version();"
alembic current

# Check resource usage
top -p $(pgrep -f "uvicorn src.main:app")
```

---

## Common Deployment Issues

### Issue: Health checks fail after deployment
**Resolution**: Check logs, verify database connectivity, restart application

### Issue: Migration fails
**Resolution**: Review migration SQL, check database locks, rollback if needed

### Issue: Performance degradation
**Resolution**: Check database query performance, review code changes, consider rollback

### Issue: Configuration errors
**Resolution**: Verify `.env` file, check environment variables, restart application

---

## Deployment Metrics

Track these metrics for each deployment:

- **Deployment Duration**: Time from start to completion
- **Downtime**: Total time application unavailable
- **Rollback Rate**: % of deployments requiring rollback
- **Time to Detect**: Time to identify deployment issues
- **Time to Recover**: Time to rollback or fix issues

---

## References

- [DATABASE_MIGRATIONS.md](./DATABASE_MIGRATIONS.md)
- [APPLICATION_LIFECYCLE.md](./APPLICATION_LIFECYCLE.md)
- [ROLLBACK_PROCEDURES.md](./ROLLBACK_PROCEDURES.md)
