# Disaster Recovery Plan

## Overview
This document outlines the disaster recovery procedures for the Quality Governance Platform.

## Recovery Objectives
- **RTO (Recovery Time Objective):** 4 hours
- **RPO (Recovery Point Objective):** 1 hour

## Backup Strategy

### Database (PostgreSQL)
- **Automated backups:** Azure Database for PostgreSQL automated backups (daily full, continuous WAL archiving)
- **Retention:** 35 days
- **Geo-redundant:** Enabled for production
- **Point-in-time restore:** Available within retention window

### Application State
- **Container images:** Stored in Azure Container Registry with geo-replication
- **Configuration:** Managed via environment variables in Azure App Service / Container Apps
- **Secrets:** Stored in Azure Key Vault with soft-delete enabled

### File Storage
- **Azure Blob Storage:** GRS (Geo-Redundant Storage) enabled
- **Immutable audit logs:** Stored with WORM (Write Once Read Many) compliance

## Recovery Procedures

### Scenario 1: Application Failure
1. Automated rollback via deployment workflow (triggered on failed smoke test)
2. Previous container image restored automatically
3. Health checks verify recovery

### Scenario 2: Database Failure
1. Initiate point-in-time restore from Azure portal
2. Update connection string in App Service configuration
3. Verify data integrity with audit trail chain verification
4. Run `POST /api/v1/audit-trail/verify` to validate hash chain

### Scenario 3: Region Failure
1. Activate geo-redundant database replica
2. Deploy application to secondary region
3. Update DNS records (Azure Traffic Manager)
4. Verify all services operational

## Testing Schedule
- **Monthly:** Application rollback drill
- **Quarterly:** Database restore verification
- **Annually:** Full region failover exercise

## Contact Information
- **On-call:** Platform Engineering Team
- **Escalation:** Infrastructure Lead
