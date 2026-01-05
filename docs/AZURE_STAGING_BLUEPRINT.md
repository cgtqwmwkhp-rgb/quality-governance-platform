# Azure Staging Blueprint - Quality Governance Platform

**Version**: 1.0  
**Last Updated**: 2026-01-05  
**Purpose**: Infrastructure blueprint for deploying the Quality Governance Platform to Azure staging environment

---

## Overview

This blueprint provides a **docs-only** reference architecture for deploying the Quality Governance Platform to Azure. It covers infrastructure components, configuration, security, and operational considerations for a staging environment.

**Deployment Options**:
1. **Azure Container Instances (ACI)** - Simple, serverless container deployment
2. **Azure App Service for Containers** - Managed PaaS with built-in scaling
3. **Azure Kubernetes Service (AKS)** - Full container orchestration (overkill for staging)

**Recommended for Staging**: Azure App Service for Containers (balance of simplicity and features)

---

## Architecture Components

### 1. Compute: Azure App Service for Containers

**Service**: Azure App Service (Linux, Container)  
**SKU**: B2 (2 cores, 3.5 GB RAM) or P1v2 (1 core, 3.5 GB RAM)  
**Scaling**: Manual or auto-scale (1-3 instances for staging)

**Configuration**:
```bash
# Resource Group
RESOURCE_GROUP="rg-qgp-staging"
LOCATION="eastus"

# App Service Plan
APP_SERVICE_PLAN="asp-qgp-staging"
SKU="B2"

# Web App
WEB_APP_NAME="qgp-staging"
CONTAINER_IMAGE="<registry>.azurecr.io/quality-governance-platform:latest"
```

**Deployment Command**:
```bash
# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create App Service Plan
az appservice plan create \
  --name $APP_SERVICE_PLAN \
  --resource-group $RESOURCE_GROUP \
  --is-linux \
  --sku $SKU

# Create Web App
az webapp create \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --deployment-container-image-name $CONTAINER_IMAGE
```

---

### 2. Database: Azure Database for PostgreSQL

**Service**: Azure Database for PostgreSQL - Flexible Server  
**SKU**: Burstable B1ms (1 vCore, 2 GiB RAM) for staging  
**Storage**: 32 GB (auto-grow enabled)  
**Backup**: 7-day retention  
**High Availability**: Disabled for staging (enable for production)

**Configuration**:
```bash
# PostgreSQL Server
POSTGRES_SERVER="psql-qgp-staging"
POSTGRES_ADMIN="qgpadmin"
POSTGRES_PASSWORD="<generate-secure-password>"
POSTGRES_DB="quality_governance_staging"
POSTGRES_VERSION="15"
```

**Deployment Command**:
```bash
# Create PostgreSQL Flexible Server
az postgres flexible-server create \
  --name $POSTGRES_SERVER \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --admin-user $POSTGRES_ADMIN \
  --admin-password $POSTGRES_PASSWORD \
  --version $POSTGRES_VERSION \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32

# Create database
az postgres flexible-server db create \
  --server-name $POSTGRES_SERVER \
  --resource-group $RESOURCE_GROUP \
  --database-name $POSTGRES_DB

# Configure firewall (allow Azure services)
az postgres flexible-server firewall-rule create \
  --name AllowAzureServices \
  --server-name $POSTGRES_SERVER \
  --resource-group $RESOURCE_GROUP \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

**Connection String**:
```
postgresql+asyncpg://{admin_user}:{password}@{server_name}.postgres.database.azure.com:5432/{database_name}?ssl=require
```

---

### 3. Container Registry: Azure Container Registry (ACR)

**Service**: Azure Container Registry  
**SKU**: Basic (sufficient for staging)  
**Admin Access**: Enabled (for simplicity in staging)

**Configuration**:
```bash
# Container Registry
ACR_NAME="acrqgpstaging"  # Must be globally unique, alphanumeric only
```

**Deployment Command**:
```bash
# Create ACR
az acr create \
  --name $ACR_NAME \
  --resource-group $RESOURCE_GROUP \
  --sku Basic \
  --admin-enabled true

# Login to ACR
az acr login --name $ACR_NAME

# Build and push image
docker build -t $ACR_NAME.azurecr.io/quality-governance-platform:latest .
docker push $ACR_NAME.azurecr.io/quality-governance-platform:latest
```

---

### 4. Secrets Management: Azure Key Vault

**Service**: Azure Key Vault  
**SKU**: Standard  
**Purpose**: Store SECRET_KEY, JWT_SECRET_KEY, database password

**Configuration**:
```bash
# Key Vault
KEY_VAULT_NAME="kv-qgp-staging"  # Must be globally unique
```

**Deployment Command**:
```bash
# Create Key Vault
az keyvault create \
  --name $KEY_VAULT_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Store secrets
az keyvault secret set --vault-name $KEY_VAULT_NAME --name "SECRET-KEY" --value "<generated-secret>"
az keyvault secret set --vault-name $KEY_VAULT_NAME --name "JWT-SECRET-KEY" --value "<generated-jwt-secret>"
az keyvault secret set --vault-name $KEY_VAULT_NAME --name "DATABASE-PASSWORD" --value "<postgres-password>"
```

**Generate Secrets**:
```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

---

### 5. Managed Identity: System-Assigned Identity

**Purpose**: Allow App Service to access Key Vault without storing credentials

**Configuration**:
```bash
# Enable system-assigned managed identity for Web App
az webapp identity assign \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP

# Get identity principal ID
IDENTITY_ID=$(az webapp identity show \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

# Grant Key Vault access to managed identity
az keyvault set-policy \
  --name $KEY_VAULT_NAME \
  --object-id $IDENTITY_ID \
  --secret-permissions get list
```

---

### 6. Application Insights: Monitoring and Logging

**Service**: Application Insights  
**Purpose**: Application performance monitoring, logging, alerting

**Configuration**:
```bash
# Application Insights
APP_INSIGHTS_NAME="appi-qgp-staging"
```

**Deployment Command**:
```bash
# Create Application Insights
az monitor app-insights component create \
  --app $APP_INSIGHTS_NAME \
  --location $LOCATION \
  --resource-group $RESOURCE_GROUP \
  --application-type web

# Get instrumentation key
INSTRUMENTATION_KEY=$(az monitor app-insights component show \
  --app $APP_INSIGHTS_NAME \
  --resource-group $RESOURCE_GROUP \
  --query instrumentationKey -o tsv)

# Configure Web App to use Application Insights
az webapp config appsettings set \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings APPINSIGHTS_INSTRUMENTATIONKEY=$INSTRUMENTATION_KEY
```

---

## Environment Configuration

### App Service Application Settings

**Configure via Azure CLI**:
```bash
az webapp config appsettings set \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    APP_ENV="staging" \
    DATABASE_URL="@Microsoft.KeyVault(SecretUri=https://${KEY_VAULT_NAME}.vault.azure.net/secrets/DATABASE-URL/)" \
    SECRET_KEY="@Microsoft.KeyVault(SecretUri=https://${KEY_VAULT_NAME}.vault.azure.net/secrets/SECRET-KEY/)" \
    JWT_SECRET_KEY="@Microsoft.KeyVault(SecretUri=https://${KEY_VAULT_NAME}.vault.azure.net/secrets/JWT-SECRET-KEY/)" \
    JWT_ALGORITHM="HS256" \
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES="30" \
    JWT_REFRESH_TOKEN_EXPIRE_DAYS="7" \
    LOG_LEVEL="INFO" \
    CORS_ORIGINS="https://qgp-staging-frontend.azurewebsites.net" \
    DATABASE_ECHO="false"
```

**Key Vault Reference Syntax**:
```
@Microsoft.KeyVault(SecretUri=https://<vault-name>.vault.azure.net/secrets/<secret-name>/)
```

---

## Database Migration Strategy

### Option 1: Startup Command (Recommended for Staging)

**Configure App Service Startup Command**:
```bash
az webapp config set \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --startup-file "sh -c 'alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000'"
```

**Pros**:
- Simple configuration
- Migrations run automatically on deployment

**Cons**:
- Application downtime during migration
- No rollback mechanism

### Option 2: Separate Migration Job (Recommended for Production)

**Use Azure Container Instances for one-off migration**:
```bash
# Run migration as a separate container
az container create \
  --name qgp-migration-job \
  --resource-group $RESOURCE_GROUP \
  --image $CONTAINER_IMAGE \
  --restart-policy Never \
  --environment-variables \
    DATABASE_URL="<connection-string>" \
  --command-line "alembic upgrade head"
```

**Pros**:
- Zero downtime deployment
- Explicit migration control
- Easy rollback

**Cons**:
- More complex deployment process

---

## Networking and Security

### 1. TLS/SSL Configuration

**App Service provides automatic TLS**:
- Free managed certificate for `*.azurewebsites.net` domain
- Custom domain support with Let's Encrypt or Azure-managed certificates

**Configuration**:
```bash
# Enforce HTTPS
az webapp update \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --https-only true

# Set minimum TLS version
az webapp config set \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --min-tls-version 1.2
```

### 2. Database Security

**PostgreSQL Flexible Server Security**:
- SSL/TLS required for all connections (enforced)
- Firewall rules restrict access to Azure services only
- Admin account should be rotated regularly
- Consider Azure AD authentication for production

**Configuration**:
```bash
# Require SSL
az postgres flexible-server parameter set \
  --server-name $POSTGRES_SERVER \
  --resource-group $RESOURCE_GROUP \
  --name require_secure_transport \
  --value ON
```

### 3. Network Isolation (Optional for Staging)

**For production, consider**:
- VNet integration for App Service
- Private endpoints for PostgreSQL and Key Vault
- Network Security Groups (NSGs)

---

## CI/CD Pipeline (GitHub Actions)

### Workflow File: `.github/workflows/deploy-staging.yml`

```yaml
name: Deploy to Azure Staging

on:
  push:
    branches:
      - main

env:
  AZURE_WEBAPP_NAME: qgp-staging
  ACR_NAME: acrqgpstaging
  IMAGE_NAME: quality-governance-platform

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Login to Azure
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Login to ACR
        run: az acr login --name ${{ env.ACR_NAME }}

      - name: Build and push Docker image
        run: |
          docker build -t ${{ env.ACR_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:${{ github.sha }} .
          docker tag ${{ env.ACR_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:${{ github.sha }} \
                     ${{ env.ACR_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:latest
          docker push ${{ env.ACR_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:${{ github.sha }}
          docker push ${{ env.ACR_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:latest

      - name: Deploy to Azure App Service
        uses: azure/webapps-deploy@v2
        with:
          app-name: ${{ env.AZURE_WEBAPP_NAME }}
          images: ${{ env.ACR_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:${{ github.sha }}

      - name: Verify deployment
        run: |
          sleep 30
          curl -f https://${{ env.AZURE_WEBAPP_NAME }}.azurewebsites.net/healthz
```

### Azure Service Principal Setup

```bash
# Create service principal for GitHub Actions
az ad sp create-for-rbac \
  --name "github-actions-qgp-staging" \
  --role contributor \
  --scopes /subscriptions/<subscription-id>/resourceGroups/$RESOURCE_GROUP \
  --sdk-auth

# Output (store in GitHub Secrets as AZURE_CREDENTIALS):
# {
#   "clientId": "...",
#   "clientSecret": "...",
#   "subscriptionId": "...",
#   "tenantId": "...",
#   ...
# }
```

---

## Cost Estimation (Monthly)

| Service | SKU | Estimated Cost (USD) |
|---------|-----|----------------------|
| App Service Plan | B2 (2 cores, 3.5 GB) | ~$70 |
| PostgreSQL Flexible Server | B1ms (1 vCore, 2 GB) | ~$15 |
| Azure Container Registry | Basic | ~$5 |
| Azure Key Vault | Standard | ~$0.03 per 10k operations |
| Application Insights | First 5 GB free | ~$0-10 |
| **Total** | | **~$90-100/month** |

**Cost Optimization**:
- Use auto-shutdown for non-business hours (can reduce App Service cost by 50%)
- Use spot instances for non-critical workloads
- Monitor and optimize Application Insights data volume

---

## Deployment Checklist

### Pre-Deployment
- [ ] Azure subscription active
- [ ] Azure CLI installed and authenticated
- [ ] Docker image built and tested locally
- [ ] Secrets generated (SECRET_KEY, JWT_SECRET_KEY)
- [ ] Resource naming conventions agreed upon

### Infrastructure Provisioning
- [ ] Create resource group
- [ ] Create Azure Container Registry
- [ ] Create Azure Database for PostgreSQL
- [ ] Create Azure Key Vault
- [ ] Create App Service Plan
- [ ] Create Web App (App Service)
- [ ] Create Application Insights

### Configuration
- [ ] Enable managed identity for Web App
- [ ] Grant Key Vault access to managed identity
- [ ] Store secrets in Key Vault
- [ ] Configure App Service application settings
- [ ] Configure startup command for migrations
- [ ] Enable HTTPS-only and set minimum TLS version

### Deployment
- [ ] Build Docker image
- [ ] Push image to ACR
- [ ] Deploy image to App Service
- [ ] Run database migrations
- [ ] Verify health endpoint
- [ ] Test API functionality

### Post-Deployment
- [ ] Configure custom domain (if applicable)
- [ ] Set up Application Insights alerts
- [ ] Configure backup retention
- [ ] Document connection strings and URLs
- [ ] Update DNS records (if applicable)

---

## Monitoring and Alerting

### Application Insights Queries

**Health Check Failures**:
```kusto
requests
| where name == "GET /healthz"
| where resultCode != "200"
| summarize count() by bin(timestamp, 5m)
```

**Database Connection Errors**:
```kusto
traces
| where message contains "database" and severityLevel >= 3
| project timestamp, message, severityLevel
```

**Response Time P95**:
```kusto
requests
| summarize percentile(duration, 95) by bin(timestamp, 5m)
```

### Recommended Alerts

1. **Health Check Failure**: Alert when `/healthz` returns non-200 for 5 minutes
2. **High Response Time**: Alert when P95 > 2000ms for 10 minutes
3. **Database Connection Failure**: Alert on any database connection errors
4. **High Memory Usage**: Alert when memory > 80% for 15 minutes

---

## Rollback Procedures

### Rollback to Previous Image

```bash
# List recent image tags
az acr repository show-tags \
  --name $ACR_NAME \
  --repository quality-governance-platform \
  --orderby time_desc \
  --top 10

# Deploy previous image
az webapp config container set \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name $ACR_NAME.azurecr.io/quality-governance-platform:<previous-sha>

# Restart Web App
az webapp restart --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP
```

### Rollback Database Migration

```bash
# Connect to Web App via SSH (if enabled)
az webapp ssh --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP

# Downgrade migration
alembic downgrade -1

# Or run downgrade via Container Instance
az container create \
  --name qgp-migration-rollback \
  --resource-group $RESOURCE_GROUP \
  --image $CONTAINER_IMAGE \
  --restart-policy Never \
  --environment-variables DATABASE_URL="<connection-string>" \
  --command-line "alembic downgrade -1"
```

---

## Troubleshooting

### Issue: Web App Not Starting

**Diagnosis**:
```bash
# View application logs
az webapp log tail --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP

# Check container logs
az webapp log show --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP
```

**Common Causes**:
- Configuration validation failure (check SECRET_KEY, DATABASE_URL)
- Database connection failure (check firewall rules)
- Key Vault access denied (check managed identity permissions)

### Issue: Database Connection Timeout

**Diagnosis**:
```bash
# Test database connectivity from Web App
az webapp ssh --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP
psql "host=$POSTGRES_SERVER.postgres.database.azure.com port=5432 dbname=$POSTGRES_DB user=$POSTGRES_ADMIN sslmode=require"
```

**Common Causes**:
- Firewall rules not configured
- SSL/TLS not enabled in connection string
- Incorrect credentials

### Issue: Key Vault Secrets Not Accessible

**Diagnosis**:
```bash
# Check managed identity assignment
az webapp identity show --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP

# Check Key Vault access policies
az keyvault show --name $KEY_VAULT_NAME --resource-group $RESOURCE_GROUP --query properties.accessPolicies
```

**Common Causes**:
- Managed identity not enabled
- Key Vault access policy not configured
- Incorrect secret URI format

---

## Security Best Practices

### 1. Secrets Management
- ✅ Use Azure Key Vault for all secrets
- ✅ Use managed identity (no credentials in code)
- ✅ Rotate secrets regularly (90-day policy)
- ✅ Never commit secrets to version control

### 2. Network Security
- ✅ Enforce HTTPS-only
- ✅ Set minimum TLS version to 1.2
- ✅ Restrict database access to Azure services only
- ✅ Use VNet integration for production

### 3. Database Security
- ✅ Require SSL for all connections
- ✅ Use strong passwords (32+ characters)
- ✅ Enable automated backups
- ✅ Consider Azure AD authentication

### 4. Monitoring and Auditing
- ✅ Enable Application Insights
- ✅ Configure alerts for failures
- ✅ Review logs regularly
- ✅ Enable Azure Security Center

---

## Next Steps (Production Deployment)

1. **High Availability**:
   - Enable zone redundancy for PostgreSQL
   - Use multiple App Service instances
   - Configure Traffic Manager for multi-region

2. **Disaster Recovery**:
   - Implement geo-replication for database
   - Set up backup region deployment
   - Document and test DR procedures

3. **Performance Optimization**:
   - Enable Azure CDN for static assets
   - Configure Redis cache for sessions
   - Implement connection pooling

4. **Security Hardening**:
   - Enable Azure DDoS Protection
   - Implement WAF (Web Application Firewall)
   - Use Private Endpoints for all services
   - Enable Azure AD authentication

---

## References

- [Azure App Service Documentation](https://docs.microsoft.com/en-us/azure/app-service/)
- [Azure Database for PostgreSQL Documentation](https://docs.microsoft.com/en-us/azure/postgresql/)
- [Azure Key Vault Documentation](https://docs.microsoft.com/en-us/azure/key-vault/)
- [Azure Container Registry Documentation](https://docs.microsoft.com/en-us/azure/container-registry/)
- [Application Insights Documentation](https://docs.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview)

---

## Appendix: Complete Deployment Script

See `scripts/deploy_azure_staging.sh` for a complete automated deployment script.
