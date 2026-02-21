# Scaling Guide

## Overview
This guide covers horizontal and vertical scaling strategies for the Quality Governance Platform.

## Architecture Components

| Component | Scaling Strategy | Current Config |
|-----------|-----------------|----------------|
| FastAPI Application | Horizontal (replicas) | 2 replicas |
| PostgreSQL | Vertical + Read Replicas | 4 vCPU, 16GB RAM |
| Redis | Vertical | 2GB cache |
| Celery Workers | Horizontal (per queue) | 2 workers |
| Celery Beat | Single instance | 1 (leader election) |

## Horizontal Scaling

### API Application
```bash
# Azure Container Apps
az containerapp update --name qgp-api --resource-group qgp-prod \
  --min-replicas 2 --max-replicas 10
```

Scale triggers:
- CPU > 70% for 5 minutes
- Request queue depth > 100
- Response time p95 > 500ms

### Celery Workers
```bash
# Scale specific queue workers
docker-compose up --scale celery-worker=4
```

Queue isolation:
- `default` queue: General tasks (2 workers)
- `email` queue: Email delivery (1 worker)
- `reports` queue: Report generation (1 worker)
- `cleanup` queue: Data retention tasks (1 worker)

## Vertical Scaling

### Database
- Monitor: Connection pool utilization, query latency, CPU usage
- Current pool: `pool_size=20, max_overflow=10`
- Scale trigger: Connection pool exhaustion > 80%

### Redis
- Monitor: Memory usage, eviction rate, connection count
- Current: `max_connections=20`
- Scale trigger: Memory usage > 80%

## Performance Baselines
- API response time p95: < 500ms
- Database query time p95: < 100ms
- Background task completion: < 30s (email), < 5min (reports)
- Health check response: < 200ms

## Monitoring
- Azure Monitor dashboards for all components
- OpenTelemetry metrics exported to Azure Monitor
- Alerts configured for scaling triggers
