# Feature Flag Governance (D19)

Lifecycle management for feature flags in the Quality Governance Platform.

## Feature Flag Architecture

| Component | Location | Purpose |
|-----------|----------|---------|
| Backend service | `src/domain/services/feature_flag_service.py` | Server-side flag evaluation |
| API routes | `src/api/routes/feature_flags.py` | CRUD management endpoints |
| Frontend consumer | `frontend/src/hooks/useFeatureFlag.ts` | Client-side flag checking |
| Database table | `feature_flags` | Flag definitions and state |

## Flag Lifecycle

```
CREATED → ENABLED (dev) → ENABLED (staging) → ENABLED (prod) → ARCHIVED → DELETED
```

| State | Description | Max Duration |
|-------|-------------|--------------|
| Created | Flag defined, disabled everywhere | 1 sprint |
| Enabled (dev) | Active in development | 2 sprints |
| Enabled (staging) | Active in staging for testing | 1 sprint |
| Enabled (prod) | Active in production | Until feature stable |
| Archived | Disabled, code references removed | 1 sprint |
| Deleted | Removed from database | — |

## Governance Rules

1. **Naming convention**: `<category>.<feature_name>` (e.g., `audit.uvdb_import`, `ui.dark_mode`)
2. **Owner required**: Every flag must have an assigned owner responsible for cleanup
3. **Expiry date**: Flags should have a target removal date (max 90 days after production enable)
4. **Cleanup PR**: When a flag is archived, a PR must remove all code references
5. **No long-lived flags**: Flags are for progressive delivery, not permanent configuration. Use environment variables for permanent config.

## Current Flags

| Flag | Category | Status | Owner | Created | Target Removal |
|------|----------|--------|-------|---------|----------------|
| `telemetry.enabled` | Observability | Disabled (prod) | Platform Eng | 2026-01 | After CORS fix |

## Review Cadence

| Frequency | Activity |
|-----------|----------|
| Sprint review | Audit active flags; identify candidates for cleanup |
| Monthly | Remove archived flags; update this document |

## Related Documents

- [`src/domain/services/feature_flag_service.py`](../../src/domain/services/feature_flag_service.py)
- [`src/api/routes/feature_flags.py`](../../src/api/routes/feature_flags.py)
- [`docs/adr/ADR-0006-environment-and-config-strategy.md`](../adr/ADR-0006-environment-and-config-strategy.md)
