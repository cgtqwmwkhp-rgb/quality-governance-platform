# Disaster Recovery Runbook

**Document Version:** 1.0  
**Last Updated:** March 2025  
**Classification:** Internal Use

---

## 1. RPO/RTO Targets

| Metric | Target | Description |
|--------|--------|-------------|
| **RPO** (Recovery Point Objective) | 1 hour | Maximum acceptable data loss. Backups should enable recovery to within 1 hour of the failure. |
| **RTO** (Recovery Time Objective) | 4 hours | Maximum acceptable downtime. Systems must be restored and operational within 4 hours of declaring a disaster. |

### Implications

- **RPO 1 hour:** Automated backups must run at least hourly, or continuous backup/WAL archiving must be enabled for point-in-time recovery.
- **RTO 4 hours:** Restore procedures, application redeployment, and validation must be completed within 4 hours. Regular DR drills are essential.

---

## 2. Database Backup Procedures

### 2.1 Azure PostgreSQL Automated Backups

Azure Database for PostgreSQL Flexible Server provides:

- **Automated daily backups** (retention configurable, typically 7–35 days)
- **Point-in-time restore (PITR)** using WAL when backup retention is enabled
- Configurable backup retention in the Azure Portal or via Azure CLI

**Verify automated backup configuration:**

```bash
az postgres flexible-server show \
  --resource-group <RESOURCE_GROUP> \
  --name <SERVER_NAME> \
  --query "{backupRetentionDays:backup.backupRetentionDays, geoRedundantBackup:backup.geoRedundantBackup}"
```

### 2.2 Manual Backup Commands

Use the backup script for on-demand backups before major changes or as part of DR preparedness:

```bash
./scripts/infra/backup_database.sh \
  --server-name <SERVER_NAME> \
  --resource-group <RESOURCE_GROUP>
```

**Direct Azure CLI command:**

```bash
az postgres flexible-server backup create \
  --resource-group <RESOURCE_GROUP> \
  --name <SERVER_NAME> \
  --backup-name backup-$(date +%Y%m%d-%H%M%S)
```

### 2.3 Backup Schedule Recommendations

| Backup Type | Frequency | Retention |
|-------------|-----------|-----------|
| Automated (Azure) | Daily | 7–35 days (per policy) |
| Manual (pre-change) | Before deployments/migrations | Keep last 5 |
| Manual (DR prep) | Weekly or before major releases | Keep last 4 |

---

## 3. Restore Procedures

### 3.1 Point-in-Time Restore (PITR)

Use when you need to recover to a specific moment within the backup retention window.

**Prerequisites:**

- Automated backups enabled
- Target restore time within retention period

**Steps:**

1. **Identify the restore point** (timestamp before the incident).

2. **Create a new server from PITR:**

```bash
az postgres flexible-server restore \
  --resource-group <RESOURCE_GROUP> \
  --name <NEW_SERVER_NAME> \
  --source-server <SOURCE_SERVER_NAME> \
  --restore-time "YYYY-MM-DDTHH:MM:SSZ"
```

3. **Update application configuration** to point to the new server hostname and credentials.

4. **Validate data** using the checklist in Section 5.

5. **Decommission or repurpose** the old server after cutover.

### 3.2 Full Restore from Backup

Use when restoring from a specific on-demand or automated backup.

**Steps:**

1. **List available backups:**

```bash
az postgres flexible-server backup list \
  --resource-group <RESOURCE_GROUP> \
  --name <SERVER_NAME> \
  --output table
```

2. **Restore to a new server** (Azure creates a new server from the backup):

```bash
az postgres flexible-server restore \
  --resource-group <RESOURCE_GROUP> \
  --name <NEW_SERVER_NAME> \
  --source-server <SOURCE_SERVER_NAME> \
  --backup-name <BACKUP_NAME>
```

3. **Update application configuration** and validate per Section 5.

---

## 4. Application Restore

### 4.1 Redeploy from Last Known Good Image

1. **Identify the last known good image/tag:**
   - Check container registry or deployment history
   - Document: `ghcr.io/<org>/<app>:<tag>` or equivalent

2. **Redeploy application:**

```bash
# Example for containerized deployment
kubectl set image deployment/<APP_NAME> <CONTAINER_NAME>=<IMAGE>:<TAG>
# Or redeploy via CI/CD pipeline using the tagged release
```

3. **Verify environment variables and secrets** are correctly configured for the restored environment.

4. **Point application to restored database** (update connection strings, config).

5. **Smoke test** critical user flows before announcing recovery.

### 4.2 Rollback Checklist

- [ ] Identify last known good release/commit
- [ ] Redeploy application from that image
- [ ] Restore/point to recovered database
- [ ] Verify config and secrets
- [ ] Run smoke tests
- [ ] Monitor logs and metrics

---

## 5. Data Validation Checklist (Post-Restore)

Complete this checklist before declaring the system recovered:

### 5.1 Database

- [ ] Database is accessible (connection test)
- [ ] Critical tables exist and have expected row counts (or within acceptable range)
- [ ] Sample queries return expected data
- [ ] No corruption errors in logs
- [ ] Indexes and constraints are intact
- [ ] Application-specific integrity checks pass (e.g., checksums, referential integrity)

### 5.2 Application

- [ ] Application starts without errors
- [ ] Health/readiness endpoints return OK
- [ ] Login/authentication works
- [ ] Critical business flows work (create, read, update as applicable)
- [ ] No unexpected errors in application logs

### 5.3 Integration

- [ ] External integrations (APIs, webhooks) function
- [ ] Scheduled jobs/cron tasks run correctly
- [ ] Monitoring and alerting are active

### 5.4 Sign-Off

- [ ] DR lead signs off on validation
- [ ] Stakeholders notified of recovery completion

---

## 6. Communication Plan During DR Events

### 6.1 Incident Declaration

When a disaster is declared:

1. **DR lead** notifies escalation contacts (Section 8).
2. **Status page / internal channel** updated with incident status.
3. **Stakeholders** informed of expected RTO and next update time.

### 6.2 Communication Cadence

| Phase | Frequency | Audience |
|-------|-----------|----------|
| Active recovery | Every 30–60 minutes | Escalation contacts, stakeholders |
| Post-recovery | Once | All stakeholders, status page |

### 6.3 Communication Channels

- **Primary:** [PLACEHOLDER: e.g., #incident-response Slack channel]
- **Escalation:** [PLACEHOLDER: e.g., PagerDuty / on-call]
- **External status:** [PLACEHOLDER: e.g., status.example.com]

### 6.4 Message Templates

**Initial notification:**

> [PLACEHOLDER] DR event declared at [TIME]. We are working to restore services. Next update in 60 minutes. RTO target: 4 hours.

**Recovery complete:**

> [PLACEHOLDER] DR recovery completed at [TIME]. Services restored. Post-incident review to follow.

---

## 7. DR Testing Schedule

| Test Type | Frequency | Scope |
|-----------|-----------|-------|
| **Full DR drill** | Quarterly | End-to-end restore, application redeploy, validation |
| **Backup verification** | Monthly | Restore to test environment, validate data |
| **Runbook review** | Quarterly | Update procedures, validate contacts |

### 7.1 Quarterly DR Drill Checklist

- [ ] Schedule drill with stakeholders (no-surprise production impact)
- [ ] Execute database restore (PITR or full) to test environment
- [ ] Redeploy application from last known good image
- [ ] Complete data validation checklist
- [ ] Document findings and update runbook
- [ ] Conduct post-drill retrospective

### 7.2 Next Scheduled DR Test

**Date:** [PLACEHOLDER: e.g., Q2 2025]  
**Owner:** [PLACEHOLDER]

---

## 8. Escalation Contacts

| Role | Name | Contact |
|------|------|---------|
| DR Lead | [PLACEHOLDER] | [PLACEHOLDER] |
| Infrastructure / DBA | [PLACEHOLDER] | [PLACEHOLDER] |
| Application Owner | [PLACEHOLDER] | [PLACEHOLDER] |
| Management / Decision Maker | [PLACEHOLDER] | [PLACEHOLDER] |

**On-call / PagerDuty:** [PLACEHOLDER]

---

## Appendix A: Quick Reference Commands

```bash
# Manual backup
./scripts/infra/backup_database.sh --server-name <SERVER> --resource-group <RG>

# List backups
az postgres flexible-server backup list -g <RG> -n <SERVER>

# PITR restore
az postgres flexible-server restore -g <RG> -n <NEW_SERVER> --source-server <SOURCE> --restore-time "YYYY-MM-DDTHH:MM:SSZ"

# Full restore from backup
az postgres flexible-server restore -g <RG> -n <NEW_SERVER> --source-server <SOURCE> --backup-name <BACKUP_NAME>
```

---

## Appendix B: Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | March 2025 | [PLACEHOLDER] | Initial runbook |
