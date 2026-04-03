# Request Correlation Guide (D13)

How to trace requests across the Quality Governance Platform stack.

## Correlation ID Flow

```
Browser → [X-Request-ID header] → FastAPI Middleware → [log enrichment] → Database queries
                                                     → [response header]
```

### Generation

- The `request_logger` middleware generates a UUID correlation ID for each request if not provided.
- If the client sends an `X-Request-ID` header, it is preserved.

### Propagation

| Layer | Mechanism | Evidence |
|-------|-----------|----------|
| Frontend → Backend | `X-Request-ID` header (optional) | `frontend/src/api/client.ts` |
| Backend middleware | `request_id` field in structured logs | `src/infrastructure/middleware/request_logger.py` |
| Backend → Database | Log correlation via request context | `src/infrastructure/database.py` |
| Response | `X-Request-ID` response header | Middleware response hook |

### Log Format

Structured JSON logs include:

```json
{
  "timestamp": "2026-01-15T10:00:00Z",
  "level": "INFO",
  "request_id": "abc-123-def",
  "method": "GET",
  "path": "/api/v1/incidents",
  "status_code": 200,
  "duration_ms": 45,
  "tenant_id": 1,
  "user_id": 5
}
```

## Tracing a Request

1. **Find the request ID** from browser DevTools (Network tab → Response Headers → `X-Request-ID`)
2. **Search backend logs** in Azure Log Analytics:
   ```kusto
   AppTraces
   | where Properties.request_id == "abc-123-def"
   | order by TimeGenerated asc
   ```
3. **Correlate with database** by matching timestamp and query patterns in slow query log.

## Dashboard Queries

Pre-built queries for Azure Log Analytics are documented in the monitoring dashboards:
- `docs/observability/dashboards/` — Grafana/Azure dashboard definitions

## Related Documents

- [`src/infrastructure/middleware/request_logger.py`](../../src/infrastructure/middleware/request_logger.py) — request logging
- [`docs/observability/alerting-rules.md`](alerting-rules.md) — alerting configuration
