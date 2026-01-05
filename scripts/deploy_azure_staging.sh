#!/usr/bin/env bash
# Quality Governance Platform - Azure Staging Deployment Script
# Purpose: Automated deployment to Azure staging environment
# Requirements: Azure CLI, Docker
# Usage: ./scripts/deploy_azure_staging.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Quality Governance Platform - Azure Staging Deployment ===${NC}"
echo ""

# Configuration
RESOURCE_GROUP="rg-qgp-staging"
LOCATION="eastus"
APP_SERVICE_PLAN="asp-qgp-staging"
WEB_APP_NAME="qgp-staging"
POSTGRES_SERVER="psql-qgp-staging"
POSTGRES_ADMIN="qgpadmin"
POSTGRES_DB="quality_governance_staging"
ACR_NAME="acrqgpstaging"
KEY_VAULT_NAME="kv-qgp-staging"
APP_INSIGHTS_NAME="appi-qgp-staging"

# Check prerequisites
echo -e "${YELLOW}[1/12] Checking prerequisites...${NC}"
if ! command -v az &> /dev/null; then
    echo -e "${RED}ERROR: Azure CLI is not installed${NC}"
    exit 1
fi
if ! command -v docker &> /dev/null; then
    echo -e "${RED}ERROR: Docker is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Prerequisites check passed${NC}"
echo ""

# Login to Azure
echo -e "${YELLOW}[2/12] Logging in to Azure...${NC}"
az account show &> /dev/null || az login
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo -e "${GREEN}✓ Logged in to Azure (Subscription: $SUBSCRIPTION_ID)${NC}"
echo ""

# Create resource group
echo -e "${YELLOW}[3/12] Creating resource group...${NC}"
az group create --name $RESOURCE_GROUP --location $LOCATION --output none
echo -e "${GREEN}✓ Resource group created: $RESOURCE_GROUP${NC}"
echo ""

# Create Azure Container Registry
echo -e "${YELLOW}[4/12] Creating Azure Container Registry...${NC}"
az acr create \
  --name $ACR_NAME \
  --resource-group $RESOURCE_GROUP \
  --sku Basic \
  --admin-enabled true \
  --output none
echo -e "${GREEN}✓ ACR created: $ACR_NAME${NC}"
echo ""

# Build and push Docker image
echo -e "${YELLOW}[5/12] Building and pushing Docker image...${NC}"
az acr login --name $ACR_NAME
COMMIT_SHA=$(git rev-parse --short HEAD)
docker build -t $ACR_NAME.azurecr.io/quality-governance-platform:$COMMIT_SHA .
docker tag $ACR_NAME.azurecr.io/quality-governance-platform:$COMMIT_SHA \
           $ACR_NAME.azurecr.io/quality-governance-platform:latest
docker push $ACR_NAME.azurecr.io/quality-governance-platform:$COMMIT_SHA
docker push $ACR_NAME.azurecr.io/quality-governance-platform:latest
echo -e "${GREEN}✓ Docker image pushed: $COMMIT_SHA${NC}"
echo ""

# Create PostgreSQL Flexible Server
echo -e "${YELLOW}[6/12] Creating PostgreSQL Flexible Server...${NC}"
echo -e "${BLUE}Generating secure password...${NC}"
POSTGRES_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
az postgres flexible-server create \
  --name $POSTGRES_SERVER \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --admin-user $POSTGRES_ADMIN \
  --admin-password "$POSTGRES_PASSWORD" \
  --version 15 \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --output none

az postgres flexible-server db create \
  --server-name $POSTGRES_SERVER \
  --resource-group $RESOURCE_GROUP \
  --database-name $POSTGRES_DB \
  --output none

az postgres flexible-server firewall-rule create \
  --name AllowAzureServices \
  --server-name $POSTGRES_SERVER \
  --resource-group $RESOURCE_GROUP \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0 \
  --output none

echo -e "${GREEN}✓ PostgreSQL server created: $POSTGRES_SERVER${NC}"
echo ""

# Create Key Vault
echo -e "${YELLOW}[7/12] Creating Azure Key Vault...${NC}"
az keyvault create \
  --name $KEY_VAULT_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --output none
echo -e "${GREEN}✓ Key Vault created: $KEY_VAULT_NAME${NC}"
echo ""

# Generate and store secrets
echo -e "${YELLOW}[8/12] Generating and storing secrets...${NC}"
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
JWT_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
DATABASE_URL="postgresql+asyncpg://${POSTGRES_ADMIN}:${POSTGRES_PASSWORD}@${POSTGRES_SERVER}.postgres.database.azure.com:5432/${POSTGRES_DB}?ssl=require"

az keyvault secret set --vault-name $KEY_VAULT_NAME --name "SECRET-KEY" --value "$SECRET_KEY" --output none
az keyvault secret set --vault-name $KEY_VAULT_NAME --name "JWT-SECRET-KEY" --value "$JWT_SECRET_KEY" --output none
az keyvault secret set --vault-name $KEY_VAULT_NAME --name "DATABASE-URL" --value "$DATABASE_URL" --output none
az keyvault secret set --vault-name $KEY_VAULT_NAME --name "DATABASE-PASSWORD" --value "$POSTGRES_PASSWORD" --output none

echo -e "${GREEN}✓ Secrets stored in Key Vault${NC}"
echo ""

# Create App Service Plan
echo -e "${YELLOW}[9/12] Creating App Service Plan...${NC}"
az appservice plan create \
  --name $APP_SERVICE_PLAN \
  --resource-group $RESOURCE_GROUP \
  --is-linux \
  --sku B2 \
  --output none
echo -e "${GREEN}✓ App Service Plan created: $APP_SERVICE_PLAN${NC}"
echo ""

# Create Web App
echo -e "${YELLOW}[10/12] Creating Web App...${NC}"
az webapp create \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --deployment-container-image-name $ACR_NAME.azurecr.io/quality-governance-platform:latest \
  --output none

# Configure ACR credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

az webapp config container set \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name $ACR_NAME.azurecr.io/quality-governance-platform:latest \
  --docker-registry-server-url https://$ACR_NAME.azurecr.io \
  --docker-registry-server-user $ACR_USERNAME \
  --docker-registry-server-password $ACR_PASSWORD \
  --output none

echo -e "${GREEN}✓ Web App created: $WEB_APP_NAME${NC}"
echo ""

# Enable managed identity and configure Key Vault access
echo -e "${YELLOW}[11/12] Configuring managed identity and Key Vault access...${NC}"
az webapp identity assign --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP --output none

IDENTITY_ID=$(az webapp identity show \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

az keyvault set-policy \
  --name $KEY_VAULT_NAME \
  --object-id $IDENTITY_ID \
  --secret-permissions get list \
  --output none

echo -e "${GREEN}✓ Managed identity configured${NC}"
echo ""

# Configure application settings
echo -e "${YELLOW}[12/12] Configuring application settings...${NC}"
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
    CORS_ORIGINS="https://${WEB_APP_NAME}.azurewebsites.net" \
    DATABASE_ECHO="false" \
  --output none

# Configure startup command (migrations + app start)
az webapp config set \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --startup-file "sh -c 'alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000'" \
  --output none

# Enable HTTPS-only
az webapp update \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --https-only true \
  --output none

echo -e "${GREEN}✓ Application settings configured${NC}"
echo ""

# Wait for deployment
echo -e "${YELLOW}Waiting for deployment to complete (60 seconds)...${NC}"
sleep 60

# Verify deployment
echo -e "${YELLOW}Verifying deployment...${NC}"
HEALTH_URL="https://${WEB_APP_NAME}.azurewebsites.net/healthz"
if curl -f -s $HEALTH_URL | grep -q '"status":"ok"'; then
    echo -e "${GREEN}✓ Health check passed!${NC}"
else
    echo -e "${RED}WARNING: Health check failed. Check application logs.${NC}"
fi
echo ""

# Summary
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo -e "${BLUE}Resource Group:${NC} $RESOURCE_GROUP"
echo -e "${BLUE}Web App URL:${NC} https://${WEB_APP_NAME}.azurewebsites.net"
echo -e "${BLUE}Health Check:${NC} https://${WEB_APP_NAME}.azurewebsites.net/healthz"
echo -e "${BLUE}PostgreSQL Server:${NC} $POSTGRES_SERVER.postgres.database.azure.com"
echo -e "${BLUE}Key Vault:${NC} $KEY_VAULT_NAME"
echo -e "${BLUE}Container Registry:${NC} $ACR_NAME"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Test API endpoints"
echo "  2. Configure custom domain (if needed)"
echo "  3. Set up Application Insights alerts"
echo "  4. Review and optimize costs"
echo ""
echo -e "${BLUE}To view logs:${NC}"
echo "  az webapp log tail --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo -e "${BLUE}To delete all resources:${NC}"
echo "  az group delete --name $RESOURCE_GROUP --yes --no-wait"
