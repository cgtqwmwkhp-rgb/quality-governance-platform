# Scaling Playbook

**Quality Governance Platform (QGP)**  
**Version:** 1.0  
**Last Updated:** 2026-03-03

---

## 1. Vertical Scaling Triggers

### When to Scale Up (Increase CPU/Memory per Replica)

| Metric | Threshold | Action |
|--------|-----------|--------|
| **CPU** | > 80% sustained for 5+ minutes | Increase CPU allocation |
| **Memory** | > 85% sustained for 5+ minutes | Increase memory allocation |
| **Request latency (p95)** | > 2s for 10+ minutes | Consider vertical scale before horizontal |

### Azure Container Apps CPU/Memory Options

| Tier | CPU | Memory |
|------|-----|--------|
| Current (default) | 0.5 vCPU | 1.0 Gi |
| Medium | 1.0 vCPU | 2.0 Gi |
| Large | 2.0 vCPU | 4.0 Gi |

### Vertical Scaling Decision Flow

1. Check if horizontal scaling (more replicas) would help first — often cheaper.
2. If single-replica bottleneck (e.g., CPU-bound processing), scale vertically.
3. Update via `az containerapp update --cpu X --memory YGi`.

---

## 2. Horizontal Scaling Rules

### Replica Bounds

| Environment | Min Replicas | Max Replicas |
|-------------|--------------|--------------|
| Staging | 1 | 3 |
| Production | 2 | 10 |

**Rule:** Min 2, max 10 replicas for production resilience.

### Scaling Triggers (Azure Container Apps)

| Trigger | Scale Out | Scale In |
|---------|-----------|----------|
| **CPU** | > 70% avg | < 30% avg |
| **Memory** | > 75% avg | < 40% avg |
| **HTTP requests** | > 100 concurrent | < 20 concurrent |
| **Custom (queue depth)** | > 50 messages | < 10 messages |

### Cooldown Periods

- **Scale out:** 60 seconds (avoid flapping)
- **Scale in:** 300 seconds (5 min) — allow traffic to stabilize before scaling down

---

## 3. Database Connection Pool Sizing

### Formula

```
max_pool_size = (replica_count × connections_per_replica) + buffer
```

### Recommended Values

| Component | Connections per Replica | Buffer |
|-----------|--------------------------|--------|
| API (FastAPI/SQLAlchemy) | 5–10 | 5 |
| Background workers | 2–5 | 2 |

### Example (4 replicas, 2 workers)

```
API: 4 × 8 + 5 = 37
Workers: 2 × 3 + 2 = 8
Total: 45 connections
```

**Database max_connections must be ≥ total pool size across all app instances.**

### Azure PostgreSQL Tiers

| Tier | Default max_connections |
|------|-------------------------|
| Basic | 50–100 |
| General Purpose | 100–5000 |
| Memory Optimized | 100–5000 |

### Pool Configuration (SQLAlchemy)

```python
# Recommended for ACA
engine = create_engine(
    DATABASE_URL,
    pool_size=5,           # per replica
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=1800,     # 30 min
)
```

---

## 4. Redis Capacity Planning

### Memory Sizing

| Use Case | Estimated Memory | Notes |
|----------|------------------|-------|
| Session store | 50–100 MB | ~1 KB per session |
| Cache (API responses) | 100–500 MB | Depends on cache hit ratio |
| Rate limiting | 10–50 MB | Minimal |
| Queue (Celery/background) | 200–1000 MB | Depends on queue depth |

### Recommended Tiers

| Environment | Redis Tier | Memory | Connections |
|-------------|------------|--------|-------------|
| Staging | Basic C0 | 250 MB | 256 |
| Production (low) | Standard C0 | 250 MB | 256 |
| Production (medium) | Standard C1 | 1 GB | 1000 |
| Production (high) | Standard C2 | 2.5 GB | 2000 |

### Connection Limits

- **Max clients:** Typically 10,000+ for Standard tier
- **Per replica:** 1–2 connections for cache, 1 for queue consumer
- **Formula:** `replica_count × 3 + workers × 2` ≤ max_clients

### Eviction Policy

- Use `allkeys-lru` for cache
- Use `volatile-lru` if mixing cache + persistent data

### Monitoring Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Memory usage | > 75% | > 90% |
| Connected clients | > 80% of max | > 95% of max |
| Hit rate | < 80% | < 60% |

---

## 5. Autoscale Script

Use `scripts/infra/autoscale_aca.sh` to configure Azure Container Apps autoscaling:

```bash
./scripts/infra/autoscale_aca.sh --min 2 --max 10 --cpu-threshold 70
./scripts/infra/autoscale_aca.sh --dry-run  # Preview changes
```

---

## 6. Quick Reference

| Resource | Command / Location |
|----------|--------------------|
| Current replica count | `az containerapp show --query properties.template.scale` |
| Autoscale script | `scripts/infra/autoscale_aca.sh` |
| Provision script | `scripts/infra/provision-aca-staging.sh` |
