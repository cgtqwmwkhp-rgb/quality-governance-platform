#!/bin/bash
#
# Production Azure Infrastructure Setup Script
# Quality Governance Platform
#
# This script creates all Azure resources needed for production deployment.
# Run this script with an authenticated Azure CLI session.
#
# Usage: ./scripts/setup_production_azure.sh
#
# Prerequisites:
#   - Azure CLI installed and authenticated (az login)
#   - Subscription with Owner/Contributor access
#   - jq installed for JSON parsing
#

set -e  # Exit on error

# ============================================================================
# CONFIGURATION - MODIFY THESE VALUES
# ============================================================================

# Azure settings
LOCATION="westeurope"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Resource names (modify as needed)
RG_NAME="rg-qgp-prod"
ACR_NAME="acrqgpprod$(openssl rand -hex 4)"  # Must be globally unique
KV_NAME="kv-qgp-prod"
APP_PLAN_NAME="plan-qgp-prod"
APP_NAME="app-qgp-prod"
SP_NAME="sp-github-qgp-prod"

# Database settings (optional - set to empty to skip)
CREATE_DATABASE="false"  # Set to "true" to create Azure PostgreSQL
DB_SERVER_NAME="qgp-prod-db"
DB_ADMIN_USER="qgpadmin"
DB_NAME="quality_governance"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI not installed. Please install: https://docs.microsoft.com/cli/azure/install-azure-cli"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_warn "jq not installed. Some output formatting may be limited."
    fi
    
    # Check Azure login
    if ! az account show &> /dev/null; then
        log_error "Not logged into Azure. Please run: az login"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
    log_info "Using subscription: $(az account show --query name -o tsv)"
    log_info "Subscription ID: $SUBSCRIPTION_ID"
}

# ============================================================================
# MAIN SETUP
# ============================================================================

main() {
    echo ""
    echo "=============================================="
    echo "  Quality Governance Platform - Production Setup"
    echo "=============================================="
    echo ""
    
    check_prerequisites
    
    # Step 1: Resource Group
    echo ""
    log_info "Step 1/6: Creating Resource Group..."
    if az group show --name $RG_NAME &> /dev/null; then
        log_warn "Resource group $RG_NAME already exists, skipping..."
    else
        az group create \
            --name $RG_NAME \
            --location $LOCATION \
            --tags Environment=Production Application=QGP \
            --output none
        log_success "Resource group created: $RG_NAME"
    fi
    
    # Step 2: Container Registry
    echo ""
    log_info "Step 2/6: Creating Azure Container Registry..."
    
    # Check if we should use existing staging ACR
    read -p "Use existing staging ACR? (Enter ACR name or press Enter to create new): " EXISTING_ACR
    
    if [ -n "$EXISTING_ACR" ]; then
        ACR_NAME=$EXISTING_ACR
        log_info "Using existing ACR: $ACR_NAME"
    else
        # Make ACR name unique
        ACR_NAME="acrqgpprod$(openssl rand -hex 4 | tr -d '\n')"
        
        az acr create \
            --resource-group $RG_NAME \
            --name $ACR_NAME \
            --sku Standard \
            --admin-enabled true \
            --output none
        log_success "ACR created: $ACR_NAME"
    fi
    
    # Get ACR credentials
    ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
    ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)
    
    # Step 3: Key Vault
    echo ""
    log_info "Step 3/6: Creating Key Vault..."
    if az keyvault show --name $KV_NAME &> /dev/null; then
        log_warn "Key Vault $KV_NAME already exists, skipping creation..."
    else
        az keyvault create \
            --resource-group $RG_NAME \
            --name $KV_NAME \
            --location $LOCATION \
            --enable-rbac-authorization false \
            --output none
        log_success "Key Vault created: $KV_NAME"
    fi
    
    # Add secrets to Key Vault
    log_info "Adding secrets to Key Vault..."
    
    # Generate secure secrets
    SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))' 2>/dev/null || openssl rand -base64 32)
    JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))' 2>/dev/null || openssl rand -base64 32)
    
    # Prompt for database URL
    echo ""
    read -p "Enter production DATABASE_URL (or press Enter to use placeholder): " DB_URL_INPUT
    
    if [ -z "$DB_URL_INPUT" ]; then
        DB_URL="postgresql+asyncpg://user:password@localhost:5432/quality_governance"
        log_warn "Using placeholder DATABASE_URL - update in Key Vault before deployment!"
    else
        DB_URL=$DB_URL_INPUT
    fi
    
    az keyvault secret set --vault-name $KV_NAME --name "DATABASE-URL" --value "$DB_URL" --output none
    az keyvault secret set --vault-name $KV_NAME --name "SECRET-KEY" --value "$SECRET_KEY" --output none
    az keyvault secret set --vault-name $KV_NAME --name "JWT-SECRET-KEY" --value "$JWT_SECRET" --output none
    
    log_success "Secrets added to Key Vault"
    
    # Step 4: App Service Plan
    echo ""
    log_info "Step 4/6: Creating App Service Plan..."
    if az appservice plan show --name $APP_PLAN_NAME --resource-group $RG_NAME &> /dev/null; then
        log_warn "App Service Plan already exists, skipping..."
    else
        az appservice plan create \
            --resource-group $RG_NAME \
            --name $APP_PLAN_NAME \
            --sku P1V2 \
            --is-linux \
            --output none
        log_success "App Service Plan created: $APP_PLAN_NAME"
    fi
    
    # Step 5: Web App
    echo ""
    log_info "Step 5/6: Creating Web App..."
    if az webapp show --name $APP_NAME --resource-group $RG_NAME &> /dev/null; then
        log_warn "Web App already exists, skipping..."
    else
        az webapp create \
            --resource-group $RG_NAME \
            --plan $APP_PLAN_NAME \
            --name $APP_NAME \
            --deployment-container-image-name mcr.microsoft.com/appsvc/staticsite:latest \
            --output none
        log_success "Web App created: $APP_NAME"
    fi
    
    # Configure Web App for ACR
    log_info "Configuring Web App for ACR..."
    az webapp config container set \
        --resource-group $RG_NAME \
        --name $APP_NAME \
        --docker-custom-image-name "${ACR_NAME}.azurecr.io/quality-governance-platform:latest" \
        --docker-registry-server-url "https://${ACR_NAME}.azurecr.io" \
        --docker-registry-server-user "$ACR_USERNAME" \
        --docker-registry-server-password "$ACR_PASSWORD" \
        --output none
    
    # Enable managed identity
    log_info "Enabling managed identity..."
    az webapp identity assign \
        --resource-group $RG_NAME \
        --name $APP_NAME \
        --output none
    
    IDENTITY_ID=$(az webapp identity show --resource-group $RG_NAME --name $APP_NAME --query principalId -o tsv)
    
    # Grant Key Vault access to Web App
    az keyvault set-policy \
        --name $KV_NAME \
        --object-id $IDENTITY_ID \
        --secret-permissions get list \
        --output none
    
    log_success "Web App configured"
    
    # Step 6: Service Principal for GitHub Actions
    echo ""
    log_info "Step 6/6: Creating Service Principal for GitHub Actions..."
    
    # Check if SP already exists
    EXISTING_SP=$(az ad sp list --display-name $SP_NAME --query "[0].appId" -o tsv 2>/dev/null)
    
    if [ -n "$EXISTING_SP" ]; then
        log_warn "Service Principal already exists. Creating new credentials..."
        SP_CREDENTIALS=$(az ad sp credential reset --id $EXISTING_SP --query "{clientId:appId, clientSecret:password, tenantId:tenant}" -o json)
        SP_APP_ID=$EXISTING_SP
    else
        SP_FULL=$(az ad sp create-for-rbac \
            --name $SP_NAME \
            --role Contributor \
            --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME \
            --sdk-auth)
        
        SP_APP_ID=$(echo $SP_FULL | jq -r '.clientId')
        SP_CREDENTIALS=$SP_FULL
    fi
    
    # Grant ACR push permission
    log_info "Granting ACR permissions..."
    az role assignment create \
        --assignee $SP_APP_ID \
        --role AcrPush \
        --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME/providers/Microsoft.ContainerRegistry/registries/$ACR_NAME \
        --output none 2>/dev/null || log_warn "ACR role may already exist"
    
    # Grant Key Vault access
    log_info "Granting Key Vault permissions..."
    az keyvault set-policy \
        --name $KV_NAME \
        --spn $SP_APP_ID \
        --secret-permissions get list \
        --output none
    
    log_success "Service Principal configured"
    
    # ============================================================================
    # OUTPUT SUMMARY
    # ============================================================================
    
    echo ""
    echo "=============================================="
    echo "  SETUP COMPLETE!"
    echo "=============================================="
    echo ""
    echo -e "${GREEN}Resources Created:${NC}"
    echo "  - Resource Group: $RG_NAME"
    echo "  - Container Registry: $ACR_NAME"
    echo "  - Key Vault: $KV_NAME"
    echo "  - App Service Plan: $APP_PLAN_NAME"
    echo "  - Web App: $APP_NAME"
    echo "  - Service Principal: $SP_NAME"
    echo ""
    echo -e "${YELLOW}Production URL:${NC}"
    echo "  https://${APP_NAME}.azurewebsites.net"
    echo ""
    echo "=============================================="
    echo "  GITHUB SECRETS TO ADD"
    echo "=============================================="
    echo ""
    echo -e "${BLUE}1. PROD_ACR_NAME:${NC}"
    echo "$ACR_NAME"
    echo ""
    echo -e "${BLUE}2. PROD_AZURE_WEBAPP_NAME:${NC}"
    echo "$APP_NAME"
    echo ""
    echo -e "${BLUE}3. AZURE_PROD_CREDENTIALS:${NC}"
    echo "$SP_CREDENTIALS"
    echo ""
    echo "=============================================="
    echo ""
    echo -e "${YELLOW}IMPORTANT: Save the credentials above securely!${NC}"
    echo ""
    
    # Save to file for reference
    OUTPUT_FILE="production_setup_output_$(date +%Y%m%d_%H%M%S).txt"
    cat > $OUTPUT_FILE << EOF
# Production Setup Output
# Generated: $(date)

## Resources
Resource Group: $RG_NAME
Container Registry: $ACR_NAME
Key Vault: $KV_NAME
App Service Plan: $APP_PLAN_NAME
Web App: $APP_NAME
Service Principal: $SP_NAME

## URLs
Production: https://${APP_NAME}.azurewebsites.net

## GitHub Secrets

### PROD_ACR_NAME
$ACR_NAME

### PROD_AZURE_WEBAPP_NAME
$APP_NAME

### AZURE_PROD_CREDENTIALS
$SP_CREDENTIALS
EOF
    
    echo -e "${GREEN}Output saved to: $OUTPUT_FILE${NC}"
    echo ""
}

# Run main
main "$@"
