# Error Response Migration Tracker (D14)

Tracking migration from plain string errors to structured error responses.

## Target Format

All API error responses should use the structured format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": {
      "errors": [
        {"field": "title", "message": "Field required", "code": "missing"}
      ]
    },
    "request_id": "abc-123-def"
  }
}
```

This envelope is produced by `src/api/middleware/error_handler.py` (`_build_envelope`).

## Migration Status by Route Module

| Module | Total Endpoints | Structured Errors | Plain String | Progress |
|--------|----------------|-------------------|--------------|----------|
| `audits.py` | 28 | 24 | 4 | 86% |
| `incidents.py` | 9 | 7 | 2 | 78% |
| `complaints.py` | 6 | 4 | 2 | 67% |
| `risks.py` | 13 | 11 | 2 | 85% |
| `actions.py` | 4 | 3 | 1 | 75% |
| `investigations.py` | 8 | 6 | 2 | 75% |
| `near_miss.py` | 9 | 7 | 2 | 78% |
| `rta.py` | 13 | 10 | 3 | 77% |
| `compliance.py` | 10 | 8 | 2 | 80% |
| `health.py` | 3 | 3 | 0 | 100% |
| `uvdb.py` | 14 | 12 | 2 | 86% |
| Other | ~20 | ~15 | ~5 | ~75% |

**Overall**: ~80% migrated to structured error responses.

## Graceful Degradation Pattern

Routes with serialization-sensitive logic (e.g., `list_findings`, `list_runs`) use a fallback pattern:

```python
try:
    validated = ResponseSchema.model_validate(item)
except Exception:
    validated = ResponseSchema(id=item.id, ...)  # minimal fallback
```

This ensures individual record failures don't crash the entire page.

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Request body validation failed |
| `NOT_FOUND` | 404 | Resource not found |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `CONFLICT` | 409 | Resource state conflict |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `SERVICE_UNAVAILABLE` | 503 | Downstream service unavailable |

## Related Documents

- [`src/api/routes/`](../../src/api/routes/) — API route modules
- [`src/domain/schemas/`](../../src/domain/schemas/) — Pydantic schemas
