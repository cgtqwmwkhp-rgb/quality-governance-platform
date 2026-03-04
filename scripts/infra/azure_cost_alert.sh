#!/usr/bin/env bash
# =============================================================================
# AZURE MONITOR COST ALERT SETUP
# =============================================================================
# Purpose: Set up Azure Monitor cost alerts using consumption budgets
# Prerequisites:
#   - Azure CLI installed and logged in
#   - Permissions: Cost Management Reader or Contributor on subscription
#
# Usage:
#   ./scripts/infra/azure_cost_alert.sh                    # Default $500 budget
#   ./scripts/infra/azure_cost_alert.sh --budget 1000       # $1000 budget
#   ./scripts/infra/azure_cost_alert.sh --dry-run          # Preview only
#   ./scripts/infra/azure_cost_alert.sh --emails a@x.com b@x.com
#
# Reference: docs/ops/COST_CAPACITY_RUNBOOK.md
# =============================================================================

set -euo pipefail

# Defaults
BUDGET_AMOUNT=500
BUDGET_NAME="qgp-monthly-budget"
DRY_RUN=false
CONTACT_EMAILS=()
RESOURCE_GROUP="${RESOURCE_GROUP:-}"
SCOPE="subscription"  # subscription or resource-group

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Set up Azure Monitor cost alerts with monthly budget and warning thresholds."
    echo ""
    echo "Options:"
    echo "  --budget AMOUNT       Monthly budget in USD (default: 500)"
    echo "  --name NAME           Budget name (default: qgp-monthly-budget)"
    echo "  --emails E1 [E2 ...]  Contact emails for alerts (space-separated)"
    echo "  --resource-group RG   Scope budget to resource group (optional)"
    echo "  --dry-run             Preview commands without executing"
    echo "  -h, --help            Show this help"
    echo ""
    echo "Thresholds: 50%, 80%, 100% (actual spend)"
    echo ""
    echo "Examples:"
    echo "  $0 --budget 500"
    echo "  $0 --budget 1000 --emails ops@example.com"
    echo "  $0 --dry-run"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --budget)
            BUDGET_AMOUNT="$2"
            shift 2
            ;;
        --name)
            BUDGET_NAME="$2"
            shift 2
            ;;
        --emails)
            shift
            while [[ $# -gt 0 ]] && [[ ! "$1" =~ ^-- ]]; do
                CONTACT_EMAILS+=("$1")
                shift
            done
            ;;
        --resource-group)
            RESOURCE_GROUP="$2"
            SCOPE="resource-group"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

# Validate
if [[ ! "$BUDGET_AMOUNT" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
    echo -e "${RED}ERROR: Budget must be a positive number${NC}"
    exit 1
fi
if [[ "$(echo "$BUDGET_AMOUNT" | awk '{print ($1 <= 0)}')" == "1" ]]; then
    echo -e "${RED}ERROR: Budget must be greater than zero${NC}"
    exit 1
fi

if [[ "$SCOPE" == "resource-group" ]] && [[ -z "$RESOURCE_GROUP" ]]; then
    echo -e "${RED}ERROR: --resource-group requires a value${NC}"
    exit 1
fi

# Date range: first of current month to end of next year
START_DATE=$(date -u +%Y-%m-01T00:00:00Z)
END_YEAR=$(($(date +%Y) + 1))
END_DATE="${END_YEAR}-12-31T23:59:59Z"

echo -e "${GREEN}=== Azure Cost Alert Setup ===${NC}"
echo ""
echo "Configuration:"
echo "  Budget: \$$BUDGET_AMOUNT/month"
echo "  Name: $BUDGET_NAME"
echo "  Thresholds: 50%, 80%, 100%"
echo "  Scope: $SCOPE"
[[ -n "$RESOURCE_GROUP" ]] && echo "  Resource Group: $RESOURCE_GROUP"
[[ ${#CONTACT_EMAILS[@]} -gt 0 ]] && echo "  Emails: ${CONTACT_EMAILS[*]}"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW}[DRY-RUN] Would execute the following:${NC}"
    echo ""
    echo "  1. Get subscription ID: az account show --query id -o tsv"
    echo ""
    echo "  2. Create budget via Azure REST API (PUT Microsoft.Consumption/budgets):"
    echo "     - Amount: $BUDGET_AMOUNT"
    echo "     - Time grain: Monthly"
    echo "     - Notifications: Actual_GreaterThan_50_Percent, Actual_GreaterThan_80_Percent, Actual_GreaterThan_100_Percent"
    if [[ ${#CONTACT_EMAILS[@]} -gt 0 ]]; then
        echo "     - Contact emails: ${CONTACT_EMAILS[*]}"
    else
        echo "     - Contact roles: Owner (subscription owners receive alerts)"
    fi
    echo ""
    echo -e "${YELLOW}[DRY-RUN] No changes applied.${NC}"
    exit 0
fi

# Check Azure login
echo -e "${YELLOW}[1/4] Checking Azure login...${NC}"
if ! az account show &> /dev/null; then
    echo -e "${RED}ERROR: Not logged in to Azure. Run 'az login' first.${NC}"
    exit 1
fi
SUB_ID=$(az account show --query id -o tsv)
echo -e "${GREEN}✓ Logged in (subscription: ${SUB_ID:0:8}...)${NC}"
echo ""

# Build notifications and request body
EMAILS_JSON="[]"
ROLES_JSON='["Owner"]'
if [[ ${#CONTACT_EMAILS[@]} -gt 0 ]]; then
    EMAILS_JSON="["
    for i in "${!CONTACT_EMAILS[@]}"; do
        [[ $i -gt 0 ]] && EMAILS_JSON+=","
        EMAILS_JSON+="\"${CONTACT_EMAILS[$i]}\""
    done
    EMAILS_JSON+="]"
    ROLES_JSON="[]"
fi
NOTIF_TEMPLATE='{"enabled":true,"operator":"GreaterThan","threshold":%s,"contactEmails":%s,"contactRoles":%s,"contactGroups":[],"thresholdType":"Actual"}'
N50=$(printf "$NOTIF_TEMPLATE" 50 "$EMAILS_JSON" "$ROLES_JSON")
N80=$(printf "$NOTIF_TEMPLATE" 80 "$EMAILS_JSON" "$ROLES_JSON")
N100=$(printf "$NOTIF_TEMPLATE" 100 "$EMAILS_JSON" "$ROLES_JSON")

BODY=$(cat <<BODY
{
  "properties": {
    "category": "Cost",
    "amount": $BUDGET_AMOUNT,
    "timeGrain": "Monthly",
    "timePeriod": {
      "startDate": "$START_DATE",
      "endDate": "$END_DATE"
    },
    "notifications": {
      "Actual_GreaterThan_50_Percent": $N50,
      "Actual_GreaterThan_80_Percent": $N80,
      "Actual_GreaterThan_100_Percent": $N100
    }
  }
}
BODY
)

# Determine scope URL
if [[ "$SCOPE" == "resource-group" ]]; then
    SCOPE_URL="/subscriptions/$SUB_ID/resourceGroups/$RESOURCE_GROUP"
    BUDGET_URI="https://management.azure.com${SCOPE_URL}/providers/Microsoft.Consumption/budgets/${BUDGET_NAME}?api-version=2019-10-01"
else
    SCOPE_URL="/subscriptions/$SUB_ID"
    BUDGET_URI="https://management.azure.com${SCOPE_URL}/providers/Microsoft.Consumption/budgets/${BUDGET_NAME}?api-version=2019-10-01"
fi

echo -e "${YELLOW}[2/4] Checking for existing budget...${NC}"
EXISTING=$(az rest --method get --url "$BUDGET_URI" 2>/dev/null || true)
if [[ -n "$EXISTING" ]] && [[ "$EXISTING" != *"ResourceNotFound"* ]] && [[ "$EXISTING" != *"Could not find"* ]]; then
    echo -e "${YELLOW}Budget '$BUDGET_NAME' exists. Updating...${NC}"
    if command -v jq &> /dev/null; then
        ETAG=$(echo "$EXISTING" | jq -r '.eTag // empty')
        if [[ -n "$ETAG" ]]; then
            BODY=$(echo "$BODY" | jq --arg etag "$ETAG" '. + {eTag: $etag}')
        fi
    fi
fi
echo ""

echo -e "${YELLOW}[3/4] Creating/updating budget...${NC}"
# Write body to temp file for az rest
TMP_BODY=$(mktemp)
trap 'rm -f "$TMP_BODY"' EXIT
echo "$BODY" > "$TMP_BODY"

if az rest --method put --url "$BUDGET_URI" --body "@${TMP_BODY}" --output none 2>/dev/null; then
    echo -e "${GREEN}✓ Budget created/updated${NC}"
else
    echo -e "${RED}ERROR: Failed to create budget. Check permissions (Cost Management Contributor) and CLI version.${NC}"
    exit 1
fi
echo ""

echo -e "${YELLOW}[4/4] Verifying...${NC}"
az consumption budget show --budget-name "$BUDGET_NAME" ${RESOURCE_GROUP:+--resource-group "$RESOURCE_GROUP"} --query "{name:name,amount:amount,timeGrain:timeGrain}" -o table 2>/dev/null || \
    az rest --method get --url "$BUDGET_URI" --query "properties.{amount:amount,timeGrain:timeGrain}" -o table 2>/dev/null || true
echo ""

echo -e "${GREEN}=== Cost alert setup complete ===${NC}"
echo ""
echo "Budget '$BUDGET_NAME' is active. Alerts will be sent when spend reaches:"
echo "  - 50% (\$$(echo "$BUDGET_AMOUNT * 0.5" | bc 2>/dev/null || echo "?") )"
echo "  - 80% (\$$(echo "$BUDGET_AMOUNT * 0.8" | bc 2>/dev/null || echo "?") )"
echo "  - 100% (\$$BUDGET_AMOUNT)"
echo ""
echo "Note: Budget evaluation runs every 24 hours. Alerts typically arrive within an hour."
echo -e "${GREEN}✓ Done${NC}"
