#!/usr/bin/env bash
# Quality Governance Platform - Reset Drill
# Purpose: Test disaster recovery by resetting and redeploying from scratch
# Requirements: Docker, docker-compose
# Usage: ./scripts/reset_drill.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${RED}=== Quality Governance Platform - Reset Drill ===${NC}"
echo -e "${YELLOW}WARNING: This will destroy all data in the sandbox environment!${NC}"
echo ""

# Confirmation prompt
read -p "Are you sure you want to proceed? (type 'yes' to confirm): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Reset drill cancelled."
    exit 0
fi
echo ""

# Step 1: Stop all services
echo -e "${YELLOW}[1/6] Stopping all services...${NC}"
docker-compose -f docker-compose.sandbox.yml down
echo -e "${GREEN}✓ Services stopped${NC}"
echo ""

# Step 2: Remove all volumes (data destruction)
echo -e "${YELLOW}[2/6] Removing all volumes (data destruction)...${NC}"
docker-compose -f docker-compose.sandbox.yml down -v
docker volume prune -f
echo -e "${GREEN}✓ Volumes removed${NC}"
echo ""

# Step 3: Remove all images
echo -e "${YELLOW}[3/6] Removing Docker images...${NC}"
docker-compose -f docker-compose.sandbox.yml down --rmi all 2>/dev/null || true
echo -e "${GREEN}✓ Images removed${NC}"
echo ""

# Step 4: Rebuild from scratch
echo -e "${YELLOW}[4/6] Rebuilding from scratch...${NC}"
docker-compose -f docker-compose.sandbox.yml build --no-cache
echo -e "${GREEN}✓ Rebuild complete${NC}"
echo ""

# Step 5: Deploy fresh environment
echo -e "${YELLOW}[5/6] Deploying fresh environment...${NC}"
docker-compose -f docker-compose.sandbox.yml up -d postgres
echo "Waiting for PostgreSQL..."
sleep 10
docker-compose -f docker-compose.sandbox.yml up migrate
docker-compose -f docker-compose.sandbox.yml up -d app
echo "Waiting for application..."
sleep 15
echo -e "${GREEN}✓ Fresh environment deployed${NC}"
echo ""

# Step 6: Verify recovery
echo -e "${YELLOW}[6/6] Verifying recovery...${NC}"
HEALTH_RESPONSE=$(curl -s http://localhost:8000/healthz)
if echo "$HEALTH_RESPONSE" | grep -q '"status":"ok"'; then
    echo -e "${GREEN}✓ Recovery verified: $HEALTH_RESPONSE${NC}"
else
    echo -e "${RED}ERROR: Recovery verification failed${NC}"
    echo "Response: $HEALTH_RESPONSE"
    docker-compose -f docker-compose.sandbox.yml logs app
    exit 1
fi
echo ""

# Summary
echo -e "${GREEN}=== Reset Drill Complete ===${NC}"
echo ""
echo "Recovery time: ~2-3 minutes"
echo "All data has been destroyed and recreated from scratch."
echo ""
echo "Services running:"
docker-compose -f docker-compose.sandbox.yml ps
echo ""
echo "Next steps:"
echo "  1. Verify application functionality"
echo "  2. Test database migrations"
echo "  3. Confirm audit logs are empty"
