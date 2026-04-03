# API Deprecation Log (D10)

Tracking deprecated API endpoints and their sunset dates.

## Active Deprecations

| Endpoint | Method | Deprecated Since | Sunset Date | Replacement | Notes |
|----------|--------|-----------------|-------------|-------------|-------|
| — | — | — | — | — | No active deprecations |

## Deprecation Policy

1. **Announcement**: Deprecated endpoints return a `Deprecation` HTTP header with the sunset date.
2. **Grace period**: Minimum 90 days between deprecation announcement and removal.
3. **Documentation**: All deprecations are logged in this file and communicated in release notes.
4. **Versioning**: The API uses URL-based versioning (`/api/v1/`). Breaking changes increment the version.

## Completed Deprecations

| Endpoint | Deprecated | Removed | Replacement |
|----------|-----------|---------|-------------|
| — | — | — | No completed deprecations yet |

## Error Model Versioning

The API error response format is standardized:

```json
{
  "detail": "Human-readable error description",
  "error_code": "MACHINE_READABLE_CODE",
  "field_errors": [{"field": "name", "message": "Required"}]
}
```

Changes to the error model follow the same deprecation policy.

## Related Documents

- [`docs/api/openapi-conventions.md`](openapi-conventions.md) — API design conventions
- [`src/api/routes/`](../../src/api/routes/) — API route definitions
