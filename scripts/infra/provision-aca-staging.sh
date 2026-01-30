#!/usr/bin/env bash
# =============================================================================
# PROVISION AZURE CONTAINER APPS STAGING
# =============================================================================
# Purpose: Create the qgp-staging Container App in ACA environment
# Prerequisites:
#   - Azure CLI installed and logged in
#   - Permissions to create Container Apps in rg-qgp-staging
#   - Key Vault kv-qgp-staging exists with required secrets
#
# Usage:
#   ./scripts/infra/provision-aca-staging.sh
#
# Reference: ADR-0004 - Azure Container Apps Staging Infrastructure
# =============================================================================

set -euo pipefail

# Configuration
RESOURCE_GROUP="rg-qgp-staging"
LOCATION="uksouth"
ACA_ENVIRONMENT="qgp-staging-env"
CONTAINER_APP_NAME="qgp-staging"
KEY_VAULT_NAME="kv-qgp-staging"
TARGET_PORT=8000
MIN_REPLICAS=1
MAX_REPLICAS=3

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Provision ACA Staging ===${NC}"
echo ""
echo "Configuration:"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location: $LOCATION"
echo "  ACA Environment: $ACA_ENVIRONMENT"
echo "  Container App: $CONTAINER_APP_NAME"
echo "  Key Vault: $KEY_VAULT_NAME"
echo "  Target Port: $TARGET_PORT"
echo ""

# Check if logged in to Azure
echo -e "${YELLOW}[1/7] Checking Azure login...${NC}"
if ! az account show &> /dev/null; then
    echo -e "${RED}ERROR: Not logged in to Azure. Run 'az login' first.${NC}"
    exit 1
fi
SUBSCRIPTION=$(az account show --query name -o tsv)
echo -e "${GREEN}✓ Logged in to: $SUBSCRIPTION${NC}"
echo ""

# Verify resource group exists
echo -e "${YELLOW}[2/7] Verifying resource group...${NC}"
if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${RED}ERROR: Resource group $RESOURCE_GROUP does not exist.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Resource group exists${NC}"
echo ""

# Verify ACA environment exists
echo -e "${YELLOW}[3/7] Verifying ACA environment...${NC}"
if ! az containerapp env show --name "$ACA_ENVIRONMENT" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${RED}ERROR: ACA environment $ACA_ENVIRONMENT does not exist.${NC}"
    echo "  You may need to create it first or check the environment name."
    exit 1
fi
echo -e "${GREEN}✓ ACA environment exists${NC}"
echo ""

# Verify Key Vault exists and has required secrets
echo -e "${YELLOW}[4/7] Verifying Key Vault secrets...${NC}"
REQUIRED_SECRETS=("DATABASE-URL" "SECRET-KEY" "JWT-SECRET-KEY")
for secret in "${REQUIRED_SECRETS[@]}"; do
    if ! az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name "$secret" &> /dev/null; then
        echo -e "${RED}ERROR: Secret $secret not found in Key Vault $KEY_VAULT_NAME${NC}"
        exit 1
    fi
    echo "  ✓ $secret exists"
done
echo -e "${GREEN}✓ All required secrets exist${NC}"
echo ""

# Check if container app already exists
echo -e "${YELLOW}[5/7] Checking if container app exists...${NC}"
if az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${YELLOW}⚠ Container app $CONTAINER_APP_NAME already exists.${NC}"
    read -p "Do you want to update it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborting."
        exit 0
    fi
    UPDATE_MODE=true
else
    UPDATE_MODE=false
fi
echo ""

# Get ACR name (assuming it's in the same resource group or a shared RG)
echo -e "${YELLOW}[6/7] Getting ACR information...${NC}"
# Try to find ACR in same RG or common patterns
ACR_NAME=$(az acr list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv 2>/dev/null || echo "")
if [ -z "$ACR_NAME" ]; then
    # Try parent resource group
    ACR_NAME=$(az acr list --query "[?contains(name, 'qgp')].name | [0]" -o tsv 2>/dev/null || echo "")
fi
if [ -z "$ACR_NAME" ]; then
    echo -e "${YELLOW}Could not auto-detect ACR. Please enter ACR name:${NC}"
    read -r ACR_NAME
fi
ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
echo -e "${GREEN}✓ Using ACR: $ACR_LOGIN_SERVER${NC}"
echo ""

# Create or update the container app
echo -e "${YELLOW}[7/7] Creating/updating container app...${NC}"

# First, create a user-assigned managed identity or use system-assigned
IDENTITY_ID=$(az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" --query "identity.principalId" -o tsv 2>/dev/null || echo "")

if [ "$UPDATE_MODE" = false ]; then
    echo "Creating new container app..."
    
    # Create with a placeholder image first (will be updated by CI/CD)
    az containerapp create \
        --name "$CONTAINER_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --environment "$ACA_ENVIRONMENT" \
        --image "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest" \
        --target-port "$TARGET_PORT" \
        --ingress external \
        --min-replicas "$MIN_REPLICAS" \
        --max-replicas "$MAX_REPLICAS" \
        --cpu 0.5 \
        --memory 1.0Gi \
        --system-assigned \
        --registry-server "$ACR_LOGIN_SERVER" \
        --env-vars \
            APP_ENV=staging \
            LOG_LEVEL=INFO \
            JWT_ALGORITHM=HS256 \
            JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30 \
            JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

    echo -e "${GREEN}✓ Container app created${NC}"
else
    echo "Updating existing container app..."
    
    az containerapp update \
        --name "$CONTAINER_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --min-replicas "$MIN_REPLICAS" \
        --max-replicas "$MAX_REPLICAS" \
        --set-env-vars \
            APP_ENV=staging \
            LOG_LEVEL=INFO \
            JWT_ALGORITHM=HS256 \
            JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30 \
            JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

    echo -e "${GREEN}✓ Container app updated${NC}"
fi

# Get the managed identity principal ID
echo ""
echo -e "${YELLOW}Configuring managed identity access to Key Vault...${NC}"
IDENTITY_PRINCIPAL_ID=$(az containerapp show \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "identity.principalId" -o tsv)

if [ -n "$IDENTITY_PRINCIPAL_ID" ]; then
    # Grant Key Vault access
    az keyvault set-policy \
        --name "$KEY_VAULT_NAME" \
        --object-id "$IDENTITY_PRINCIPAL_ID" \
        --secret-permissions get list \
        --output none
    echo -e "${GREEN}✓ Key Vault access granted to managed identity${NC}"
else
    echo -e "${YELLOW}⚠ Could not get managed identity principal ID. Manual KV access setup may be needed.${NC}"
fi

# Configure secrets from Key Vault
echo ""
echo -e "${YELLOW}Configuring secrets from Key Vault...${NC}"

# Get Key Vault URI
KV_URI=$(az keyvault show --name "$KEY_VAULT_NAME" --query "properties.vaultUri" -o tsv)

# Note: ACA supports Key Vault references via the identity
# For now, we'll fetch secrets and set them as ACA secrets (encrypted at rest)
# In production, consider using Dapr secret stores for true KV integration

DB_URL=$(az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name "DATABASE-URL" --query "value" -o tsv)
SECRET_KEY=$(az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name "SECRET-KEY" --query "value" -o tsv)
JWT_SECRET=$(az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name "JWT-SECRET-KEY" --query "value" -o tsv)

az containerapp secret set \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --secrets \
        database-url="$DB_URL" \
        secret-key="$SECRET_KEY" \
        jwt-secret-key="$JWT_SECRET" \
    --output none

echo -e "${GREEN}✓ Secrets configured${NC}"

# Update container app to use secrets as environment variables
az containerapp update \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --set-env-vars \
        DATABASE_URL=secretref:database-url \
        SECRET_KEY=secretref:secret-key \
        JWT_SECRET_KEY=secretref:jwt-secret-key \
    --output none

echo -e "${GREEN}✓ Environment variables linked to secrets${NC}"

# Get the FQDN
echo ""
echo -e "${YELLOW}Getting container app details...${NC}"
FQDN=$(az containerapp show \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.configuration.ingress.fqdn" -o tsv)

REVISION=$(az containerapp show \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.latestRevisionName" -o tsv)

echo ""
echo -e "${GREEN}=== Container App Provisioned ===${NC}"
echo ""
echo "Details:"
echo "  Name: $CONTAINER_APP_NAME"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Environment: $ACA_ENVIRONMENT"
echo "  FQDN: https://$FQDN"
echo "  Latest Revision: $REVISION"
echo ""
echo "Next steps:"
echo "  1. Push the actual application image via deploy-staging workflow"
echo "  2. Verify endpoints return 200:"
echo "     curl https://$FQDN/healthz"
echo "     curl https://$FQDN/readyz"
echo "  3. Run contract probe to verify"
echo ""
echo -e "${GREEN}✓ Provisioning complete${NC}"
