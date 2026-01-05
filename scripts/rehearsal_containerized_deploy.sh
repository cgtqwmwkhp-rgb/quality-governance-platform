#!/usr/bin/env bash
# Quality Governance Platform - Containerized Deployment Rehearsal
# Purpose: Rehearse full containerized deployment lifecycle
# Requirements: Docker, docker-compose
# Usage: ./scripts/rehearsal_containerized_deploy.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Quality Governance Platform - Deployment Rehearsal ===${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}[1/8] Checking prerequisites...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}ERROR: docker is not installed${NC}"
    exit 1
fi
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}ERROR: docker-compose is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker and docker-compose are available${NC}"
echo ""

# Clean up any existing containers/volumes
echo -e "${YELLOW}[2/8] Cleaning up existing containers and volumes...${NC}"
docker-compose -f docker-compose.sandbox.yml down -v 2>/dev/null || true
echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""

# Build the Docker image
echo -e "${YELLOW}[3/8] Building Docker image...${NC}"
docker-compose -f docker-compose.sandbox.yml build --no-cache
echo -e "${GREEN}✓ Docker image built successfully${NC}"
echo ""

# Start PostgreSQL
echo -e "${YELLOW}[4/8] Starting PostgreSQL...${NC}"
docker-compose -f docker-compose.sandbox.yml up -d postgres
echo "Waiting for PostgreSQL to be ready..."
sleep 10
docker-compose -f docker-compose.sandbox.yml exec -T postgres pg_isready -U qgp_user -d quality_governance_sandbox
echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
echo ""

# Run migrations
echo -e "${YELLOW}[5/8] Running database migrations...${NC}"
docker-compose -f docker-compose.sandbox.yml up migrate
MIGRATE_EXIT_CODE=$(docker inspect qgp-migrate-sandbox --format='{{.State.ExitCode}}')
if [ "$MIGRATE_EXIT_CODE" != "0" ]; then
    echo -e "${RED}ERROR: Migration failed with exit code $MIGRATE_EXIT_CODE${NC}"
    docker-compose -f docker-compose.sandbox.yml logs migrate
    exit 1
fi
echo -e "${GREEN}✓ Migrations applied successfully${NC}"
echo ""

# Start application
echo -e "${YELLOW}[6/8] Starting application...${NC}"
docker-compose -f docker-compose.sandbox.yml up -d app
echo "Waiting for application to be ready..."
sleep 15

# Health check
echo -e "${YELLOW}[7/8] Running health checks...${NC}"
HEALTH_RESPONSE=$(curl -s http://localhost:8000/healthz)
if echo "$HEALTH_RESPONSE" | grep -q '"status":"ok"'; then
    echo -e "${GREEN}✓ Health check passed: $HEALTH_RESPONSE${NC}"
else
    echo -e "${RED}ERROR: Health check failed${NC}"
    echo "Response: $HEALTH_RESPONSE"
    docker-compose -f docker-compose.sandbox.yml logs app
    exit 1
fi
echo ""

# Verify database connectivity
echo -e "${YELLOW}[8/8] Verifying database connectivity...${NC}"
docker-compose -f docker-compose.sandbox.yml exec -T postgres psql -U qgp_user -d quality_governance_sandbox -c "SELECT COUNT(*) FROM alembic_version;"
echo -e "${GREEN}✓ Database connectivity verified${NC}"
echo ""

# Summary
echo -e "${GREEN}=== Deployment Rehearsal Complete ===${NC}"
echo ""
echo "Services running:"
docker-compose -f docker-compose.sandbox.yml ps
echo ""
echo "To view logs:"
echo "  docker-compose -f docker-compose.sandbox.yml logs -f app"
echo ""
echo "To test the API:"
echo "  curl http://localhost:8000/healthz"
echo ""
echo "To stop all services:"
echo "  docker-compose -f docker-compose.sandbox.yml down"
echo ""
echo "To stop and remove volumes (full reset):"
echo "  docker-compose -f docker-compose.sandbox.yml down -v"
