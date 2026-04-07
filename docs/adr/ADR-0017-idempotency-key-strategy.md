# ADR-0017: Idempotency Key Strategy for Mutating API Operations

**Status**: Accepted  
**Date**: 2026-04-07  
**Decision Makers**: Platform Team  

## Context

The platform handles high-stakes write operations — incident creation, complaint registration, CAPA creation, evidence upload — where network retries or duplicate client submissions must not create duplicate records or corrupt business state.

Idempotency is required for:
1. Mobile / poor-connectivity clients that retry failed requests
2. Integration partners using webhook retry logic
3. Internal async task queues that may re-submit on timeout
4. GDPR Article 17 erasure requests (must be idempotent — double-erasure must not fail)

Without a formal idempotency strategy, duplicate submissions caused `409 Conflict` inconsistencies or silent duplicate records depending on route implementation.

## Decision

We implement idempotency at the **HTTP middleware layer** via `src/api/middleware/idempotency.py`:

1. **Scope**: `POST`, `PUT`, and `PATCH` methods only (idempotent by HTTP semantics: `GET`, `DELETE`)
2. **Key**: Clients supply an `Idempotency-Key: <uuid>` request header
3. **Storage**: Redis (in-memory cache) — key: `idem:<Idempotency-Key>`, TTL: 24 hours
4. **Deduplication**: Payload hash (SHA-256) is stored alongside the cached response. Same key + same hash → replay. Same key + different hash → `409 IDEMPOTENCY_CONFLICT`
5. **Error code**: `IDEMPOTENCY_CONFLICT` (defined in `src/domain/error_codes.py`) is returned on hash mismatch
6. **Tenant isolation**: Current implementation namespaces by `Idempotency-Key` value only. Tenant isolation relies on auth middleware preventing cross-tenant access before idempotency is checked. Full tenant-scoped key (`tenant_id:idempotency_key`) is tracked as a follow-on item (AP-24).

## Consequences

**Positive:**
- All mutating endpoints benefit from idempotency without per-route implementation
- The `IDEMPOTENCY_CONFLICT` error code provides actionable signal to clients
- Redis TTL prevents unbounded cache growth

**Negative:**
- Requires Redis to be available; if Redis is down, idempotency is bypassed (fail-open)
- Payload hashing means JSON key order must be consistent (documented in API style guide)
- No tenant-level key scoping yet — mitigated by auth layer but noted as technical debt

## Alternatives Considered

- Per-route idempotency with `external_ref` fields: partial approach still exists for complaints; this ADR generalises it at middleware level
- Database-level unique constraints: more durable but slower and schema-invasive
- No idempotency (rely on client deduplication): rejected — insufficient for GDPR erasure and integration partners
