#!/bin/bash
#
# GitHub Production Secrets Configuration Script
# 
# This script helps configure GitHub repository secrets for production deployment.
# It requires the GitHub CLI (gh) to be installed and authenticated.
#
# Usage: ./scripts/configure_github_production.sh
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo "=============================================="
echo "  GitHub Production Configuration"
echo "=============================================="
echo ""

# Check prerequisites
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) not installed${NC}"
    echo "Install from: https://cli.github.com/"
    exit 1
fi

if ! gh auth status &> /dev/null; then
    echo -e "${RED}Error: Not authenticated to GitHub${NC}"
    echo "Run: gh auth login"
    exit 1
fi

# Get repository
REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null)

if [ -z "$REPO" ]; then
    echo -e "${YELLOW}Not in a git repository with GitHub remote${NC}"
    read -p "Enter repository (owner/repo): " REPO
fi

echo -e "${BLUE}Repository: $REPO${NC}"
echo ""

# ============================================================================
# SECRETS CONFIGURATION
# ============================================================================

echo "--- Configure Production Secrets ---"
echo ""
echo "You will need the following values from Azure setup:"
echo "  1. Production ACR name"
echo "  2. Production Web App name"
echo "  3. Service Principal credentials (JSON)"
echo ""

# Secret 1: PROD_ACR_NAME
read -p "Enter PROD_ACR_NAME (e.g., acrqgpprod): " ACR_NAME
if [ -n "$ACR_NAME" ]; then
    echo "$ACR_NAME" | gh secret set PROD_ACR_NAME --repo "$REPO"
    echo -e "${GREEN}✓ PROD_ACR_NAME set${NC}"
else
    echo -e "${YELLOW}Skipped PROD_ACR_NAME${NC}"
fi

# Secret 2: PROD_AZURE_WEBAPP_NAME
read -p "Enter PROD_AZURE_WEBAPP_NAME (e.g., app-qgp-prod): " WEBAPP_NAME
if [ -n "$WEBAPP_NAME" ]; then
    echo "$WEBAPP_NAME" | gh secret set PROD_AZURE_WEBAPP_NAME --repo "$REPO"
    echo -e "${GREEN}✓ PROD_AZURE_WEBAPP_NAME set${NC}"
else
    echo -e "${YELLOW}Skipped PROD_AZURE_WEBAPP_NAME${NC}"
fi

# Secret 3: AZURE_PROD_CREDENTIALS
echo ""
echo "For AZURE_PROD_CREDENTIALS, paste the full JSON from:"
echo "  az ad sp create-for-rbac --sdk-auth"
echo ""
echo "Paste JSON (end with Ctrl+D on empty line):"
CREDS=$(cat)

if [ -n "$CREDS" ]; then
    echo "$CREDS" | gh secret set AZURE_PROD_CREDENTIALS --repo "$REPO"
    echo -e "${GREEN}✓ AZURE_PROD_CREDENTIALS set${NC}"
else
    echo -e "${YELLOW}Skipped AZURE_PROD_CREDENTIALS${NC}"
fi

echo ""

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================

echo "--- Configure Production Environment ---"
echo ""

# Check if environment exists
ENV_EXISTS=$(gh api repos/$REPO/environments/production 2>/dev/null || echo "")

if [ -z "$ENV_EXISTS" ]; then
    echo "Creating 'production' environment..."
    
    # Create environment (minimal - reviewers must be added via UI)
    gh api --method PUT repos/$REPO/environments/production \
        -f wait_timer=0 \
        -F reviewers='[]' 2>/dev/null || true
    
    echo -e "${GREEN}✓ Environment 'production' created${NC}"
else
    echo -e "${BLUE}Environment 'production' already exists${NC}"
fi

echo ""
echo -e "${YELLOW}NOTE: Add required reviewers via GitHub UI:${NC}"
echo "  https://github.com/$REPO/settings/environments"
echo ""

# ============================================================================
# VERIFICATION
# ============================================================================

echo "--- Verification ---"
echo ""

echo "Current secrets:"
gh secret list --repo "$REPO" | grep -E "PROD_|AZURE_PROD" || echo "  (none found)"
echo ""

echo "Current environments:"
gh api repos/$REPO/environments --jq '.environments[].name' 2>/dev/null || echo "  (none found)"
echo ""

# ============================================================================
# SUMMARY
# ============================================================================

echo "=============================================="
echo "  NEXT STEPS"
echo "=============================================="
echo ""
echo "1. Verify staging is working:"
echo "   ./scripts/smoke_test.sh https://<staging-app>.azurewebsites.net"
echo ""
echo "2. Add required reviewers for production environment:"
echo "   https://github.com/$REPO/settings/environments"
echo ""
echo "3. Trigger production deployment:"
echo "   gh workflow run deploy-production.yml --repo $REPO"
echo "   OR"
echo "   Create a release tag: git tag v1.0.0 && git push origin v1.0.0"
echo ""
