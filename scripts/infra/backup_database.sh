#!/usr/bin/env bash
#
# Azure PostgreSQL Flexible Server - On-Demand Backup Script
#
# Creates an on-demand backup of an Azure PostgreSQL Flexible Server.
# Requires: Azure CLI (az) installed and logged in.
#
# Usage:
#   ./backup_database.sh --server-name <SERVER> --resource-group <RG>
#   ./backup_database.sh --server-name <SERVER> --resource-group <RG> --dry-run
#

set -euo pipefail

# Defaults
DRY_RUN=false
SERVER_NAME=""
RESOURCE_GROUP=""
LOG_PREFIX="[backup_database]"

# Logging
log_info() {
  echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") $LOG_PREFIX INFO: $*"
}

log_error() {
  echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") $LOG_PREFIX ERROR: $*" >&2
}

log_status() {
  echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") $LOG_PREFIX $*"
}

usage() {
  cat <<EOF
Usage: $(basename "$0") --server-name <SERVER> --resource-group <RG> [--dry-run]

Required:
  --server-name, -s    Name of the Azure PostgreSQL Flexible Server
  --resource-group, -g Name of the Azure resource group

Optional:
  --dry-run            Show what would be executed without creating a backup

Examples:
  $(basename "$0") --server-name mypgserver --resource-group my-rg
  $(basename "$0") -s mypgserver -g my-rg --dry-run
EOF
  exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --server-name|-s)
      SERVER_NAME="$2"
      shift 2
      ;;
    --resource-group|-g)
      RESOURCE_GROUP="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      log_error "Unknown option: $1"
      usage
      ;;
  esac
done

# Validate required parameters
if [[ -z "$SERVER_NAME" ]] || [[ -z "$RESOURCE_GROUP" ]]; then
  log_error "Missing required parameters: --server-name and --resource-group are required"
  usage
fi

# Generate backup name with timestamp
BACKUP_NAME="backup-$(date +%Y%m%d-%H%M%S)"

log_info "Starting backup process for server: $SERVER_NAME (resource group: $RESOURCE_GROUP)"
log_info "Backup name: $BACKUP_NAME"

if [[ "$DRY_RUN" == true ]]; then
  log_status "DRY RUN - Would execute:"
  log_status "  az postgres flexible-server backup create \\"
  log_status "    --resource-group $RESOURCE_GROUP \\"
  log_status "    --name $SERVER_NAME \\"
  log_status "    --backup-name $BACKUP_NAME"
  log_info "Dry run complete. No backup created."
  exit 0
fi

# Check Azure CLI is available
if ! command -v az &>/dev/null; then
  log_error "Azure CLI (az) is not installed or not in PATH"
  exit 1
fi

# Create backup
log_info "Creating backup..."
if az postgres flexible-server backup create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$SERVER_NAME" \
  --backup-name "$BACKUP_NAME"; then
  log_info "Backup created successfully: $BACKUP_NAME"
  log_status "SUCCESS: Backup $BACKUP_NAME completed for server $SERVER_NAME"
  exit 0
else
  EXIT_CODE=$?
  log_error "Backup failed with exit code: $EXIT_CODE"
  log_status "FAILED: Backup creation failed for server $SERVER_NAME"
  exit "$EXIT_CODE"
fi
