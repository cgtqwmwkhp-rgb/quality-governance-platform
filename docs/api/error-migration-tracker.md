# Error Response Migration Tracker (D14)

Tracking migration from plain string errors to structured error responses.

## Target Format

All API error responses should use the structured format:

```json
{
  "detail": "Human-readable description",
  "error_code": "VALIDATION_ERROR",
  "field_errors": [
    {"field": "title", "message": "Field required", "code": "missing"}
  ]
}
```

## Migration Status by Route Module

| Module | Total Endpoints | Structured Errors | Plain String | Progress |
|--------|----------------|-------------------|--------------|----------|
| `audits.py` | 12 | 10 | 2 | 83% |
| `incidents.py` | 8 | 6 | 2 | 75% |
| `complaints.py` | 6 | 4 | 2 | 67% |
| `risks.py` | 6 | 5 | 1 | 83% |
| `actions.py` | 6 | 4 | 2 | 67% |
| `investigations.py` | 8 | 6 | 2 | 75% |
| `near_miss.py` | 5 | 3 | 2 | 60% |
| `rta.py` | 5 | 3 | 2 | 60% |
| `compliance.py` | 4 | 3 | 1 | 75% |
| `health.py` | 3 | 3 | 0 | 100% |
| `uvdb.py` | 5 | 4 | 1 | 80% |
| Other | ~15 | ~10 | ~5 | ~67% |

**Overall**: ~75% migrated to structured error responses.

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
