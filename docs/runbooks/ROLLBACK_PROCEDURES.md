# Rollback Procedures Runbook

**Purpose**: Emergency rollback procedures for failed deployments  
**Audience**: DevOps, SRE, On-Call Engineers  
**Last Updated**: 2026-01-04

---

## When to Rollback

Rollback immediately if:
- Critical functionality is broken
- Data corruption detected
- Security vulnerability introduced
- System stability compromised
- Performance degradation >50%

---

## Rollback Decision Tree

```
Deployment Failed?
├─ Database migration failed?
│  ├─ Yes → Use Database Rollback (Option 1)
│  └─ No → Continue
├─ Application code issue?
│  ├─ Yes → Use Application Rollback (Option 2)
│  └─ No → Continue
└─ Configuration issue?
   └─ Yes → Use Configuration Rollback (Option 3)
```

---

## Option 1: Database Rollback

### Scenario
Database migration failed or caused data issues

### Procedure

```bash
# 1. Stop application
systemctl stop quality-governance-platform

# 2. Rollback migration (preferred)
alembic downgrade -1

# 3. Verify migration version
alembic current

# 4. Restart application
systemctl start quality-governance-platform

# 5. Verify health
curl http://localhost:8000/readyz
```

### Alternative: Database Restore

```bash
# 1. Stop application
systemctl stop quality-governance-platform

# 2. Restore from backup
pg_restore -h $DB_HOST -U $DB_USER -d $DB_NAME -c backup_YYYYMMDD_HHMMSS.dump

# 3. Restart application
systemctl start quality-governance-platform
```

**Time Estimate**: 5-15 minutes  
**Downtime**: Yes (application stopped during rollback)

---

## Option 2: Application Rollback

### Scenario
New application code introduced bugs or regressions

### Procedure

```bash
# 1. Identify last known good version
git log --oneline -10

# 2. Checkout previous version
git checkout <previous_commit_sha>

# 3. Restart application
systemctl restart quality-governance-platform

# 4. Verify health
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz

# 5. Monitor logs
tail -f /var/log/quality-governance-platform/app.log
```

**Time Estimate**: 2-5 minutes  
**Downtime**: Minimal (restart only)

---

## Option 3: Configuration Rollback

### Scenario
Configuration change caused issues

### Procedure

```bash
# 1. Restore previous .env file
cp .env.backup .env

# 2. Restart application
systemctl restart quality-governance-platform

# 3. Verify configuration
curl http://localhost:8000/readyz
```

**Time Estimate**: 1-2 minutes  
**Downtime**: Minimal (restart only)

---

## Post-Rollback Checklist

- [ ] Verify application health checks passing
- [ ] Check application logs for errors
- [ ] Test critical functionality
- [ ] Notify stakeholders of rollback
- [ ] Document rollback reason
- [ ] Create incident report
- [ ] Schedule post-mortem

---

## Rollback Prevention

**Before Deployment**:
- Test in staging environment
- Review all changes
- Backup database
- Document rollback plan

**During Deployment**:
- Monitor logs in real-time
- Run smoke tests
- Verify health checks

**After Deployment**:
- Monitor for 30 minutes
- Check error rates
- Verify performance metrics

---

## Emergency Contacts

- **On-Call Engineer**: [Contact]
- **Database Team**: [Contact]
- **Escalation**: [Contact]
