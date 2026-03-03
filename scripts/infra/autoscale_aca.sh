#!/usr/bin/env bash
# =============================================================================
# AZURE CONTAINER APPS AUTOSCALE CONFIGURATION
# =============================================================================
# Purpose: Configure min/max replicas and CPU/memory scaling rules for ACA
# Prerequisites:
#   - Azure CLI installed and logged in
#   - Permissions to update Container Apps
#
# Usage:
#   ./scripts/infra/autoscale_aca.sh --min 2 --max 10 --cpu-threshold 70
#   ./scripts/infra/autoscale_aca.sh --dry-run
#
# Reference: docs/ops/SCALING_PLAYBOOK.md
# =============================================================================

set -euo pipefail

# Default configuration (matches provision-aca-staging.sh)
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-qgp-staging}"
CONTAINER_APP_NAME="${CONTAINER_APP_NAME:-qgp-staging}"

# Default scaling values (min 2, max 10 per SCALING_PLAYBOOK.md)
MIN_REPLICAS=2
MAX_REPLICAS=10
CPU_THRESHOLD=70
MEMORY_THRESHOLD=75
DRY_RUN=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Configure Azure Container Apps autoscaling."
    echo ""
    echo "Options:"
    echo "  --min N              Minimum replicas (default: 2)"
    echo "  --max N              Maximum replicas (default: 10)"
    echo "  --cpu-threshold N    CPU % threshold for scale-out (default: 70)"
    echo "  --memory-threshold N Memory % threshold for scale-out (default: 75)"
    echo "  --dry-run            Preview changes without applying"
    echo "  --app NAME           Container app name (default: qgp-staging)"
    echo "  --resource-group RG  Resource group (default: rg-qgp-staging)"
    echo "  -h, --help           Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 --min 2 --max 10 --cpu-threshold 70"
    echo "  $0 --dry-run"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --min)
            MIN_REPLICAS="$2"
            shift 2
            ;;
        --max)
            MAX_REPLICAS="$2"
            shift 2
            ;;
        --cpu-threshold)
            CPU_THRESHOLD="$2"
            shift 2
            ;;
        --memory-threshold)
            MEMORY_THRESHOLD="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --app)
            CONTAINER_APP_NAME="$2"
            shift 2
            ;;
        --resource-group)
            RESOURCE_GROUP="$2"
            shift 2
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
if [[ "$MIN_REPLICAS" -lt 0 ]] || [[ "$MAX_REPLICAS" -lt 1 ]]; then
    echo -e "${RED}ERROR: Invalid replica counts (min >= 0, max >= 1)${NC}"
    exit 1
fi
if [[ "$MIN_REPLICAS" -gt "$MAX_REPLICAS" ]]; then
    echo -e "${RED}ERROR: min-replicas cannot exceed max-replicas${NC}"
    exit 1
fi
if [[ "$CPU_THRESHOLD" -lt 1 ]] || [[ "$CPU_THRESHOLD" -gt 100 ]]; then
    echo -e "${RED}ERROR: cpu-threshold must be 1-100${NC}"
    exit 1
fi
if [[ "$MEMORY_THRESHOLD" -lt 1 ]] || [[ "$MEMORY_THRESHOLD" -gt 100 ]]; then
    echo -e "${RED}ERROR: memory-threshold must be 1-100${NC}"
    exit 1
fi

echo -e "${GREEN}=== ACA Autoscale Configuration ===${NC}"
echo ""
echo "Target:"
echo "  Container App: $CONTAINER_APP_NAME"
echo "  Resource Group: $RESOURCE_GROUP"
echo ""
echo "Scaling configuration:"
echo "  Min replicas: $MIN_REPLICAS"
echo "  Max replicas: $MAX_REPLICAS"
echo "  CPU threshold: ${CPU_THRESHOLD}%"
echo "  Memory threshold: ${MEMORY_THRESHOLD}%"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW}[DRY-RUN] Would execute the following commands:${NC}"
    echo ""
    echo "  # 1. Update replica limits"
    echo "  az containerapp update \\"
    echo "    --name $CONTAINER_APP_NAME \\"
    echo "    --resource-group $RESOURCE_GROUP \\"
    echo "    --min-replicas $MIN_REPLICAS \\"
    echo "    --max-replicas $MAX_REPLICAS"
    echo ""
    echo "  # 2. Configure CPU scaling rule"
    echo "  az containerapp update \\"
    echo "    --name $CONTAINER_APP_NAME \\"
    echo "    --resource-group $RESOURCE_GROUP \\"
    echo "    --scale-rule-name cpu-rule \\"
    echo "    --scale-rule-type cpu \\"
    echo "    --scale-rule-metadata type=Utilization value=$CPU_THRESHOLD"
    echo ""
    echo "  # 3. Configure memory scaling rule"
    echo "  az containerapp update \\"
    echo "    --name $CONTAINER_APP_NAME \\"
    echo "    --resource-group $RESOURCE_GROUP \\"
    echo "    --scale-rule-name memory-rule \\"
    echo "    --scale-rule-type memory \\"
    echo "    --scale-rule-metadata type=Utilization value=$MEMORY_THRESHOLD"
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
echo -e "${GREEN}✓ Logged in${NC}"
echo ""

# Verify container app exists
echo -e "${YELLOW}[2/4] Verifying container app exists...${NC}"
if ! az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${RED}ERROR: Container app $CONTAINER_APP_NAME not found in $RESOURCE_GROUP${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Container app exists${NC}"
echo ""

# Update replica limits
echo -e "${YELLOW}[3/4] Updating min/max replicas...${NC}"
az containerapp update \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --min-replicas "$MIN_REPLICAS" \
    --max-replicas "$MAX_REPLICAS" \
    --output none
echo -e "${GREEN}✓ Replica limits updated${NC}"
echo ""

# Configure CPU scaling rule
# Note: Azure CLI may only apply one custom rule per update; we apply CPU first
echo -e "${YELLOW}[4/4] Configuring CPU scaling rule...${NC}"
az containerapp update \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --scale-rule-name cpu-rule \
    --scale-rule-type cpu \
    --scale-rule-metadata "type=Utilization" "value=$CPU_THRESHOLD" \
    --output none
echo -e "${GREEN}✓ CPU rule configured (scale out when CPU > ${CPU_THRESHOLD}%)${NC}"
echo ""

# Configure memory scaling rule (separate update due to CLI limitation)
echo -e "${YELLOW}Configuring memory scaling rule...${NC}"
az containerapp update \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --scale-rule-name memory-rule \
    --scale-rule-type memory \
    --scale-rule-metadata "type=Utilization" "value=$MEMORY_THRESHOLD" \
    --output none
echo -e "${GREEN}✓ Memory rule configured (scale out when memory > ${MEMORY_THRESHOLD}%)${NC}"
echo ""

echo -e "${GREEN}=== Autoscale configuration complete ===${NC}"
echo ""
echo "Current scale configuration:"
az containerapp show \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.template.scale" -o table
echo ""
echo -e "${GREEN}✓ Done${NC}"
