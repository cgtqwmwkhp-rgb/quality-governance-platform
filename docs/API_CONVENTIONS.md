# API Conventions

## URL Structure
- All endpoints: `/api/v1/{resource}`
- Plural nouns for collections: `/api/v1/incidents/`
- Singular with ID for items: `/api/v1/incidents/{id}`

## Request/Response Standards
- All responses use JSON
- List endpoints return arrays with pagination metadata
- Timestamps use ISO 8601 with timezone (UTC)
- IDs use UUID v4

## Authentication
- Bearer token in Authorization header
- Azure AD SSO for production
- JWT tokens with configurable expiry

## Error Responses
```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "timestamp": "2026-03-03T12:00:00Z"
}
```

## Pagination
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "has_next": true
}
```

## Versioning
- URL-based versioning: `/api/v1/`, `/api/v2/`
- Breaking changes require new version
- Deprecation notice: 6 months before removal

## Rate Limiting
- Default: 60 requests/minute per IP
- Auth endpoints: 10 requests/minute
- Header: `Retry-After` on 429 responses
