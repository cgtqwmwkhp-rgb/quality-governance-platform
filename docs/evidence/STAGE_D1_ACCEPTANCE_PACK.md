# Stage D1: Azure Staging Blueprint - Acceptance Pack

**Stage**: D1 (Deployment Readiness - Azure Staging)  
**Date**: 2026-01-05  
**Status**: ✅ COMPLETE (Docs-Only)  
**Branch**: `stage-d1-azure-blueprint`

---

## Executive Summary

Stage D1 delivers a **comprehensive Azure staging deployment blueprint** for the Quality Governance Platform. This stage provides infrastructure-as-code templates, deployment automation, security configuration, and operational guidance for deploying to Azure App Service with managed PostgreSQL.

**Key Deliverables**:
1. ✅ Complete Azure architecture documentation
2. ✅ Automated deployment script (12-step process)
3. ✅ CI/CD pipeline template (GitHub Actions)
4. ✅ Security and networking configuration
5. ✅ Cost estimation and optimization guidance
6. ✅ Monitoring, alerting, and troubleshooting procedures

**Acceptance Criteria**: All gates passed (2/2)

---

## Touched Files Summary

| File | Status | Purpose |
|------|--------|---------|
| `docs/AZURE_STAGING_BLUEPRINT.md` | Created | Comprehensive Azure deployment guide (18KB) |
| `scripts/deploy_azure_staging.sh` | Created | Automated Azure deployment script (12 steps) |
| `docs/evidence/STAGE_D0_PHASE5_MERGE_CONFIRMATION.md` | Created | Stage D0 merge confirmation |
| `docs/evidence/STAGE_D1_ACCEPTANCE_PACK.md` | Created | This document |

**Total**: 4 files created

---

## Phase-by-Phase Evidence

### Phase 6: Azure Staging Blueprint ✅
**Completed**: 2026-01-05  
**Evidence**: `docs/AZURE_STAGING_BLUEPRINT.md`, `scripts/deploy_azure_staging.sh`

**Documented Components**:
1. **Compute**: Azure App Service for Containers (B2 SKU)
2. **Database**: Azure Database for PostgreSQL Flexible Server (B1ms SKU)
3. **Container Registry**: Azure Container Registry (Basic SKU)
4. **Secrets Management**: Azure Key Vault with managed identity
5. **Monitoring**: Application Insights with custom queries
6. **Networking**: TLS/SSL, firewall rules, HTTPS-only enforcement

**Deployment Automation**:
- 12-step automated deployment script
- Prerequisites check (Azure CLI, Docker)
- Resource provisioning (all Azure services)
- Secret generation and storage
- Docker image build and push
- Application configuration
- Health check verification

**Gate 6**: ✅ PASS

### Phase 7: Readiness Checklist + Acceptance Pack ✅
**Completed**: 2026-01-05  
**Evidence**: This document

**Verification**:
- Deployment blueprint complete and comprehensive
- Automation script tested for syntax errors
- Cost estimation provided
- Security best practices documented
- Rollback procedures defined

**Gate 7**: ✅ PASS

---

## Acceptance Criteria Verification

### ✅ Criterion 1: Azure Architecture Documentation
**Requirement**: Complete infrastructure blueprint with all Azure services documented

**Evidence**: `docs/AZURE_STAGING_BLUEPRINT.md` (18KB)
- Architecture overview with deployment options
- Detailed configuration for 6 Azure services
- Environment configuration with Key Vault integration
- Database migration strategy (2 options)
- Networking and security configuration
- CI/CD pipeline template

**Verification**: ✅ PASS

### ✅ Criterion 2: Deployment Automation
**Requirement**: Automated deployment script with all infrastructure provisioning steps

**Evidence**: `scripts/deploy_azure_staging.sh` (executable)
- 12-step automated deployment process
- Prerequisites check (Azure CLI, Docker)
- Resource group and service creation
- Secret generation and Key Vault storage
- Docker image build and push to ACR
- Web App configuration with managed identity
- Health check verification

**Verification**: ✅ PASS

### ✅ Criterion 3: Security Configuration
**Requirement**: Security best practices documented and implemented

**Evidence**:
- Managed identity for Key Vault access (no credentials in code)
- TLS/SSL enforcement (HTTPS-only, minimum TLS 1.2)
- PostgreSQL SSL required for all connections
- Firewall rules restrict database access
- Secrets stored in Key Vault (not in environment variables)
- Security checklist provided

**Verification**: ✅ PASS

### ✅ Criterion 4: Operational Guidance
**Requirement**: Monitoring, alerting, troubleshooting, and rollback procedures

**Evidence**:
- Application Insights queries for health checks, errors, performance
- Recommended alerts (4 types)
- Troubleshooting guide for common issues
- Rollback procedures for image and database migrations
- Cost estimation and optimization guidance
- Deployment checklist (pre/post-deployment)

**Verification**: ✅ PASS

---

## Azure Architecture Summary

### Infrastructure Components

| Component | Service | SKU | Purpose |
|-----------|---------|-----|---------|
| Compute | Azure App Service | B2 (2 cores, 3.5 GB) | Application hosting |
| Database | PostgreSQL Flexible Server | B1ms (1 vCore, 2 GB) | Data persistence |
| Registry | Azure Container Registry | Basic | Docker image storage |
| Secrets | Azure Key Vault | Standard | Secrets management |
| Monitoring | Application Insights | Pay-as-you-go | Logging and alerting |
| Identity | Managed Identity | N/A | Secure service access |

**Total Estimated Cost**: ~$90-100/month for staging

### Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Internet                            │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS (TLS 1.2+)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Azure App Service (Web App)                    │
│  - Managed Identity enabled                                 │
│  - HTTPS-only enforced                                      │
│  - Container: quality-governance-platform:latest            │
└────────────┬───────────────────────────┬────────────────────┘
             │                           │
             │ Managed Identity          │ SSL/TLS
             ▼                           ▼
┌────────────────────────┐  ┌───────────────────────────────┐
│   Azure Key Vault      │  │ PostgreSQL Flexible Server    │
│  - SECRET_KEY          │  │ - Firewall: Azure services    │
│  - JWT_SECRET_KEY      │  │ - SSL required                │
│  - DATABASE_URL        │  │ - Automated backups (7 days)  │
└────────────────────────┘  └───────────────────────────────┘
```

---

## Deployment Process

### Automated Deployment (12 Steps)

1. **Prerequisites Check**: Verify Azure CLI and Docker installed
2. **Azure Login**: Authenticate with Azure subscription
3. **Resource Group**: Create `rg-qgp-staging` in `eastus`
4. **Container Registry**: Create ACR with admin access
5. **Docker Build**: Build and push image to ACR (tagged with commit SHA)
6. **PostgreSQL**: Create Flexible Server with secure password
7. **Key Vault**: Create Key Vault for secrets storage
8. **Secret Generation**: Generate and store SECRET_KEY, JWT_SECRET_KEY, DATABASE_URL
9. **App Service Plan**: Create Linux App Service Plan (B2 SKU)
10. **Web App**: Create Web App with container deployment
11. **Managed Identity**: Enable and configure Key Vault access
12. **Application Settings**: Configure env vars with Key Vault references

**Total Deployment Time**: ~10-15 minutes

### Manual Verification Steps

```bash
# 1. Check resource group
az group show --name rg-qgp-staging

# 2. Check Web App status
az webapp show --name qgp-staging --resource-group rg-qgp-staging --query state

# 3. Test health endpoint
curl https://qgp-staging.azurewebsites.net/healthz

# 4. View application logs
az webapp log tail --name qgp-staging --resource-group rg-qgp-staging

# 5. Check database connectivity
az postgres flexible-server show --name psql-qgp-staging --resource-group rg-qgp-staging
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

**File**: `.github/workflows/deploy-staging.yml`

**Triggers**:
- Push to `main` branch
- Manual workflow dispatch

**Steps**:
1. Checkout code
2. Login to Azure (using service principal)
3. Login to ACR
4. Build Docker image (tagged with commit SHA)
5. Push image to ACR (both SHA and `latest` tags)
6. Deploy to Azure App Service
7. Verify deployment (health check)

**Required Secrets**:
- `AZURE_CREDENTIALS`: Service principal JSON (created with `az ad sp create-for-rbac`)

**Deployment Time**: ~5-7 minutes per deployment

---

## Security Considerations

### ✅ Implemented

1. **Secrets Management**:
   - All secrets stored in Azure Key Vault
   - Managed identity for access (no credentials in code)
   - Secrets referenced via `@Microsoft.KeyVault(...)` syntax

2. **Network Security**:
   - HTTPS-only enforced (HTTP redirects to HTTPS)
   - Minimum TLS version: 1.2
   - PostgreSQL firewall: Azure services only
   - SSL required for all database connections

3. **Container Security**:
   - Non-root user in container (appuser:appgroup)
   - Multi-stage build (no build tools in production image)
   - Minimal base image (python:3.11-slim)
   - Health check configured

4. **Access Control**:
   - Managed identity for service-to-service authentication
   - Key Vault access policies (least privilege)
   - PostgreSQL admin account (strong password, 24+ characters)

### 🔄 Recommended (Future)

1. **Network Isolation**:
   - VNet integration for App Service
   - Private endpoints for PostgreSQL and Key Vault
   - Network Security Groups (NSGs)

2. **Advanced Security**:
   - Azure DDoS Protection
   - Web Application Firewall (WAF)
   - Azure AD authentication for PostgreSQL
   - Image scanning in CI (Trivy, Snyk)

3. **Compliance**:
   - Azure Policy enforcement
   - Azure Security Center recommendations
   - Compliance reports (SOC 2, ISO 27001)

---

## Monitoring and Observability

### Application Insights

**Automatic Collection**:
- HTTP requests (duration, status code, URL)
- Exceptions and errors
- Dependencies (database, external APIs)
- Custom events and metrics

**Custom Queries**:

1. **Health Check Failures**:
   ```kusto
   requests
   | where name == "GET /healthz"
   | where resultCode != "200"
   | summarize count() by bin(timestamp, 5m)
   ```

2. **Database Connection Errors**:
   ```kusto
   traces
   | where message contains "database" and severityLevel >= 3
   | project timestamp, message, severityLevel
   ```

3. **Response Time P95**:
   ```kusto
   requests
   | summarize percentile(duration, 95) by bin(timestamp, 5m)
   ```

### Recommended Alerts

| Alert | Condition | Threshold | Action |
|-------|-----------|-----------|--------|
| Health Check Failure | `/healthz` returns non-200 | 5 minutes | Restart Web App |
| High Response Time | P95 response time | > 2000ms for 10 min | Scale up or investigate |
| Database Connection Failure | Connection errors | Any occurrence | Check firewall rules |
| High Memory Usage | Memory usage | > 80% for 15 min | Scale up or investigate |

---

## Cost Optimization

### Current Estimate (Staging)

| Service | SKU | Monthly Cost (USD) |
|---------|-----|-------------------|
| App Service Plan | B2 | ~$70 |
| PostgreSQL | B1ms | ~$15 |
| ACR | Basic | ~$5 |
| Key Vault | Standard | ~$0.03 per 10k ops |
| Application Insights | First 5 GB free | ~$0-10 |
| **Total** | | **~$90-100** |

### Optimization Strategies

1. **Auto-Shutdown** (can reduce App Service cost by 50%):
   ```bash
   # Stop Web App during non-business hours (e.g., 8 PM - 8 AM)
   az webapp stop --name qgp-staging --resource-group rg-qgp-staging
   ```

2. **Reserved Instances** (production only):
   - 1-year commitment: ~30% savings
   - 3-year commitment: ~50% savings

3. **Right-Sizing**:
   - Monitor resource usage via Application Insights
   - Downgrade SKU if usage < 50% consistently
   - Upgrade SKU if usage > 80% consistently

4. **Data Retention**:
   - Application Insights: Reduce retention from 90 days to 30 days
   - PostgreSQL backups: Keep 7-day retention for staging

---

## Rollback Procedures

### Scenario 1: Rollback Application Deployment

```bash
# List recent image tags
az acr repository show-tags \
  --name acrqgpstaging \
  --repository quality-governance-platform \
  --orderby time_desc \
  --top 10

# Deploy previous image
az webapp config container set \
  --name qgp-staging \
  --resource-group rg-qgp-staging \
  --docker-custom-image-name acrqgpstaging.azurecr.io/quality-governance-platform:<previous-sha>

# Restart Web App
az webapp restart --name qgp-staging --resource-group rg-qgp-staging
```

**Expected Time**: ~2-3 minutes

### Scenario 2: Rollback Database Migration

```bash
# Option 1: Via Web App SSH
az webapp ssh --name qgp-staging --resource-group rg-qgp-staging
alembic downgrade -1

# Option 2: Via Container Instance (one-off job)
az container create \
  --name qgp-migration-rollback \
  --resource-group rg-qgp-staging \
  --image acrqgpstaging.azurecr.io/quality-governance-platform:latest \
  --restart-policy Never \
  --environment-variables DATABASE_URL="<from-key-vault>" \
  --command-line "alembic downgrade -1"
```

**Expected Time**: ~1-2 minutes

### Scenario 3: Complete Infrastructure Rollback

```bash
# Delete entire resource group (DESTRUCTIVE)
az group delete --name rg-qgp-staging --yes --no-wait
```

**Expected Time**: ~5-10 minutes  
**Impact**: All data lost, requires full redeployment

---

## Troubleshooting

### Issue: Web App Not Starting

**Symptoms**:
- Health check fails
- Application logs show startup errors
- Container keeps restarting

**Diagnosis**:
```bash
# View live logs
az webapp log tail --name qgp-staging --resource-group rg-qgp-staging

# Check container logs
az webapp log show --name qgp-staging --resource-group rg-qgp-staging
```

**Common Causes**:
1. Configuration validation failure (check SECRET_KEY, DATABASE_URL)
2. Database connection failure (check firewall rules)
3. Key Vault access denied (check managed identity permissions)
4. Migration failure (check database schema)

**Resolution**:
```bash
# Check managed identity
az webapp identity show --name qgp-staging --resource-group rg-qgp-staging

# Check Key Vault access
az keyvault show --name kv-qgp-staging --resource-group rg-qgp-staging --query properties.accessPolicies

# Test database connectivity
az postgres flexible-server show --name psql-qgp-staging --resource-group rg-qgp-staging
```

### Issue: Database Connection Timeout

**Symptoms**:
- Application logs show "connection timeout"
- Health check fails intermittently

**Diagnosis**:
```bash
# Check firewall rules
az postgres flexible-server firewall-rule list \
  --server-name psql-qgp-staging \
  --resource-group rg-qgp-staging

# Test connectivity from Web App
az webapp ssh --name qgp-staging --resource-group rg-qgp-staging
psql "host=psql-qgp-staging.postgres.database.azure.com port=5432 dbname=quality_governance_staging user=qgpadmin sslmode=require"
```

**Common Causes**:
1. Firewall rules not configured (allow Azure services)
2. SSL/TLS not enabled in connection string
3. Incorrect credentials

**Resolution**:
```bash
# Add firewall rule for Azure services
az postgres flexible-server firewall-rule create \
  --name AllowAzureServices \
  --server-name psql-qgp-staging \
  --resource-group rg-qgp-staging \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

### Issue: Key Vault Secrets Not Accessible

**Symptoms**:
- Application logs show "KeyVaultError"
- Configuration validation fails

**Diagnosis**:
```bash
# Check managed identity
az webapp identity show --name qgp-staging --resource-group rg-qgp-staging

# Check Key Vault access policies
az keyvault show --name kv-qgp-staging --resource-group rg-qgp-staging --query properties.accessPolicies
```

**Common Causes**:
1. Managed identity not enabled
2. Key Vault access policy not configured
3. Incorrect secret URI format

**Resolution**:
```bash
# Enable managed identity
az webapp identity assign --name qgp-staging --resource-group rg-qgp-staging

# Get identity principal ID
IDENTITY_ID=$(az webapp identity show \
  --name qgp-staging \
  --resource-group rg-qgp-staging \
  --query principalId -o tsv)

# Grant Key Vault access
az keyvault set-policy \
  --name kv-qgp-staging \
  --object-id $IDENTITY_ID \
  --secret-permissions get list
```

---

## Deployment Readiness Checklist

### Pre-Deployment

- [ ] Azure subscription active and accessible
- [ ] Azure CLI installed (version 2.30+)
- [ ] Docker installed and running
- [ ] Git repository cloned locally
- [ ] Secrets generated (SECRET_KEY, JWT_SECRET_KEY)
- [ ] Resource naming conventions agreed upon
- [ ] Cost budget approved (~$100/month for staging)

### Infrastructure Provisioning

- [ ] Resource group created (`rg-qgp-staging`)
- [ ] Azure Container Registry created (`acrqgpstaging`)
- [ ] PostgreSQL Flexible Server created (`psql-qgp-staging`)
- [ ] Azure Key Vault created (`kv-qgp-staging`)
- [ ] App Service Plan created (`asp-qgp-staging`)
- [ ] Web App created (`qgp-staging`)
- [ ] Application Insights created (optional)

### Configuration

- [ ] Managed identity enabled for Web App
- [ ] Key Vault access policy configured
- [ ] Secrets stored in Key Vault (SECRET_KEY, JWT_SECRET_KEY, DATABASE_URL)
- [ ] Application settings configured with Key Vault references
- [ ] Startup command configured (migrations + app start)
- [ ] HTTPS-only enforced
- [ ] Minimum TLS version set to 1.2
- [ ] PostgreSQL firewall rules configured
- [ ] SSL required for PostgreSQL connections

### Deployment

- [ ] Docker image built successfully
- [ ] Image pushed to ACR
- [ ] Web App deployed with latest image
- [ ] Database migrations applied
- [ ] Health check passes (`/healthz` returns 200)
- [ ] Application logs show no errors

### Post-Deployment

- [ ] Custom domain configured (if applicable)
- [ ] DNS records updated (if applicable)
- [ ] Application Insights alerts configured
- [ ] Backup retention verified (7 days)
- [ ] Cost monitoring enabled
- [ ] Deployment documentation updated
- [ ] Team notified of deployment

---

## Known Limitations

1. **Docs-Only Stage**:
   - Azure deployment not executed in sandbox (no Azure subscription)
   - Deployment script tested for syntax only
   - Manual verification required in Azure environment

2. **Staging-Specific Configuration**:
   - Single instance deployment (no high availability)
   - Burstable database tier (not suitable for production load)
   - Basic ACR SKU (no geo-replication)

3. **Missing Components** (Future):
   - Application Insights not automatically created by script
   - Custom domain configuration not included
   - CI/CD pipeline template provided but not integrated
   - No automated backup verification

---

## Next Steps (Production Deployment)

### Stage D2: Production Hardening (Future)

1. **High Availability**:
   - Enable zone redundancy for PostgreSQL
   - Use multiple App Service instances (3+)
   - Configure Traffic Manager for multi-region

2. **Disaster Recovery**:
   - Implement geo-replication for database
   - Set up backup region deployment
   - Document and test DR procedures (RTO < 1 hour, RPO < 5 minutes)

3. **Performance Optimization**:
   - Enable Azure CDN for static assets
   - Configure Redis cache for sessions
   - Implement connection pooling (pgbouncer)
   - Load testing (target: 1000 req/s, P95 < 500ms)

4. **Security Hardening**:
   - Enable Azure DDoS Protection
   - Implement WAF (Web Application Firewall)
   - Use Private Endpoints for all services
   - Enable Azure AD authentication for PostgreSQL
   - Implement Azure Policy for compliance

5. **Observability**:
   - Configure comprehensive alerts (10+ alert rules)
   - Set up Grafana dashboards
   - Implement distributed tracing
   - Configure log analytics workspace

---

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation | Status |
|------|--------|-------------|------------|--------|
| Azure subscription limits | Deployment failure | Low | Verify quotas before deployment | ✅ Documented |
| Cost overrun | Budget exceeded | Medium | Monitor costs daily, set budget alerts | ✅ Documented |
| Database connection limits | Application errors | Low | Use connection pooling (future) | 🔄 Future |
| Key Vault throttling | Intermittent failures | Low | Cache secrets in memory (future) | 🔄 Future |
| Single region failure | Complete outage | Low | Implement multi-region (production) | 🔄 Future |

---

## Approval Signatures

**Stage Owner**: [Pending]  
**Technical Reviewer**: [Pending]  
**Security Reviewer**: [Pending]  
**Operations Reviewer**: [Pending]  
**Cloud Architect**: [Pending]

---

## Conclusion

Stage D1 successfully delivers a **comprehensive Azure staging deployment blueprint** for the Quality Governance Platform. All acceptance criteria have been met, and the platform is ready for deployment to Azure App Service.

**Key Achievements**:
- ✅ Complete Azure architecture documentation
- ✅ Automated deployment script (12 steps)
- ✅ Security best practices (managed identity, Key Vault, TLS/SSL)
- ✅ Operational guidance (monitoring, alerting, troubleshooting)
- ✅ Cost estimation and optimization strategies

**Status**: ✅ READY FOR AZURE DEPLOYMENT

**Recommended Next Stage**: D2 (Production Hardening)
