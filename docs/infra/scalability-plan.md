# Scalability & Capacity Plan (D25)

This document describes how the Quality Governance Platform scales on Azure, how database connections are pooled, capacity guidance by concurrent users, load-test expectations, known bottlenecks, autoscale configuration, and CDN usage.

## Current Architecture

| Layer | Technology |
|--------|------------|
| Application | Azure App Service (B2) |
| Database | Azure Database for PostgreSQL Flexible Server (Burstable B2s) |
| Cache | Azure Cache for Redis 6 |
| Object storage | Azure Blob Storage |
| Front-end / static hosting | Azure Static Web Apps |

## Connection Pool Configuration

Async PostgreSQL connections are configured in `src/infrastructure/database.py` (non-test, PostgreSQL URLs):

| Setting | Value |
|---------|--------|
| `pool_size` | 10 |
| `max_overflow` | 20 |
| `pool_pre_ping` | `True` |
| `pool_recycle` | 1800 |
| `pool_timeout` | 30 |

Together, `pool_size` and `max_overflow` allow up to **30** concurrent checked-out connections **per application instance** before the pool blocks or times out (subject to `pool_timeout`).

## Horizontal Scaling Strategy

### App Service

- **Scale-out**: When average **CPU > 70%** for **5 minutes**, add **one** instance.
- **Scale-in**: When average **CPU < 30%** for **10 minutes**, remove **one** instance.
- **Bounds**: minimum **2**, maximum **6** instances (default **2**).

Implement via Azure Monitor autoscale on the App Service plan; see **Auto-Scaling ARM Template** below and `scripts/infra/autoscale-settings.json`.

### PostgreSQL Flexible Server

Recommended vertical path as load grows:

1. **Burstable B2s** (baseline)
2. **General Purpose Gen5, 4 vCores** (`GP_Gen5_4`)
3. **General Purpose Gen5, 8 vCores** (`GP_Gen5_8`)

Revisit storage IOPS and connection limits whenever changing tier.

### Azure Cache for Redis

Recommended upgrade path:

1. **Basic C1** (dev / light traffic)
2. **Standard C2** (HA, higher throughput)
3. **Premium P1** (persistence options, better isolation, higher ceiling)

## Capacity Planning Table

Indicative sizing and **estimated monthly cost (USD, order-of-magnitude; verify with [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/) for region and commitment)**.

| Concurrent users | App Service plan (indicative) | PostgreSQL tier (indicative) | Redis tier (indicative) | Est. monthly cost (USD) |
|------------------|-------------------------------|------------------------------|-------------------------|---------------------------|
| 100 | B2, 2 instances | Burstable B2s | Basic C1 | ~$150–$300 |
| 500 | B2–S1, 2–3 instances | B2s → GP_Gen5_4 | Standard C1–C2 | ~$400–$800 |
| 1,000 | S1–P1v2, 3–4 instances | GP_Gen5_4 | Standard C2 | ~$900–$1,800 |
| 5,000 | P1v2–P2v2, 5–6 instances (autoscale cap) | GP_Gen5_8 (or higher) | Premium P1+ | ~$2,500–$5,500+ |

Costs exclude CDN, bandwidth surcharges, backup retention, and reserved-instance discounts. Tune instance count using CPU/memory profiles and load tests.

## Load Test Baseline

- **Suite**: `tests/performance/locustfile.py` (Locust).
- **Run example**: `locust -f tests/performance/locustfile.py --host=https://<api-host>`.
- **Targets**:
  - **p99** latency **< 500 ms** for API calls under agreed concurrency and think-time.
  - **p95** latency **< 200 ms** under the same profile.

Record host, user count, ramp rate, and duration with each baseline so regressions are comparable.

## Bottleneck Analysis

| Area | Risk |
|------|------|
| **DB connection pool** | Each instance can hold up to **30** pool connections (`pool_size` + `max_overflow`). Many instances × 30 can approach PostgreSQL `max_connections`; monitor active connections and pool wait time. |
| **Redis** | Redis is **single-threaded** for command execution; hot keys and large payloads can cap throughput before CPU on app nodes does. |
| **Blob Storage** | **Throughput** and per-second request limits can become a limiter for heavy upload/download or many small operations; use appropriate access patterns, batching, and tier (Hot/Cool) as needed. |

## Auto-Scaling ARM Template

The following snippet defines a `Microsoft.Insights/autoscaleSettings` resource for an App Service plan using **CpuPercentage** rules. Replace parameter placeholders and merge into your main ARM/Bicep deployment. The same logic is maintained in `scripts/infra/autoscale-settings.json`.

```json
{
  "type": "Microsoft.Insights/autoscaleSettings",
  "apiVersion": "2022-10-01",
  "name": "[parameters('autoscaleSettingName')]",
  "location": "[parameters('location')]",
  "properties": {
    "enabled": true,
    "targetResourceUri": "[resourceId('Microsoft.Web/serverfarms', parameters('appServicePlanName'))]",
    "profiles": [
      {
        "name": "cpu-based-default",
        "capacity": {
          "minimum": "2",
          "maximum": "6",
          "default": "2"
        },
        "rules": [
          {
            "metricTrigger": {
              "metricName": "CpuPercentage",
              "metricResourceUri": "[resourceId('Microsoft.Web/serverfarms', parameters('appServicePlanName'))]",
              "timeGrain": "PT1M",
              "statistic": "Average",
              "timeWindow": "PT5M",
              "timeAggregation": "Average",
              "operator": "GreaterThan",
              "threshold": 70
            },
            "scaleAction": {
              "direction": "Increase",
              "type": "ChangeCount",
              "value": "1",
              "cooldown": "PT5M"
            }
          },
          {
            "metricTrigger": {
              "metricName": "CpuPercentage",
              "metricResourceUri": "[resourceId('Microsoft.Web/serverfarms', parameters('appServicePlanName'))]",
              "timeGrain": "PT1M",
              "statistic": "Average",
              "timeWindow": "PT10M",
              "timeAggregation": "Average",
              "operator": "LessThan",
              "threshold": 30
            },
            "scaleAction": {
              "direction": "Decrease",
              "type": "ChangeCount",
              "value": "1",
              "cooldown": "PT5M"
            }
          }
        ]
      }
    ]
  }
}
```

## CDN Strategy

- **Static assets**: Served through **Azure CDN** and/or **Azure Static Web Apps** edge delivery so browsers fetch JS/CSS/images from locations close to users.
- **API responses**: **Not** cached on CDN by default—treat API endpoints as dynamic; use application-level caching (Redis) only where correctness and TTL policies are explicit.
