# Deploy Verification Determinism

## Overview

This runbook documents the deterministic deploy verification pattern used to prevent false failures caused by Azure App Service container swap latency.

## Problem Statement

Azure App Service container restarts/swaps can take 10-120 seconds. During this period:
- The old container may still serve some requests
- The new container is warming up
- Load balancer may route requests to either container

A single-shot verification immediately after deploy can hit the old container, causing false failures.

## Solution: Stability Gate Pattern

The `scripts/verify_deploy_deterministic.sh` script implements:

1. **Polling with Exponential Backoff**: Starts at 5s intervals, caps at 30s
2. **Stability Gate**: Requires N consecutive matching SHA responses (default: 3)
3. **Bounded Retries**: Maximum 30 attempts or 10 minute timeout
4. **Clear Stop Conditions**: Success requires both SHA match AND health check pass

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--stability` | 3 | Consecutive matching responses required |
| `--max-attempts` | 30 | Maximum poll attempts |
| `--timeout` | 600 | Total timeout in seconds |

## Evidence Output

The script produces structured JSON evidence:

```json
{
  "verification_result": "PASS",
  "expected_sha": "abc123...",
  "final_sha": "abc123...",
  "stability_confirmations": 3,
  "health_status": "PASS",
  "attempts": 5,
  "elapsed_seconds": 45
}
```

## Troubleshooting

### Verification Times Out

If verification consistently times out:

1. Check Azure App Service health: `az webapp show --name <name> --resource-group <rg>`
2. Check container logs: `az webapp log tail --name <name> --resource-group <rg>`
3. Verify the meta/version endpoint is implemented and returns `build_sha`

### Stability Gate Never Reaches N

If responses alternate between old/new SHA:

1. Azure may be in mid-swap - wait and retry
2. Check if multiple container instances exist
3. Consider increasing stability requirement

## Related ADRs

- ADR-0001: Quality gates (unit/integration/security) - unchanged
- ADR-0002: Fail-fast config validation - unchanged

## Changelog

- 2026-01-27: Initial implementation to fix run #21392643904 false failure
