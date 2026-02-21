# ADR-0008: JWT Token Revocation via Database Blacklist

**Status:** Accepted
**Date:** 2026-02-21
**Authors:** Platform Engineering Team

## Context

The platform uses stateless JWT tokens for authentication, which by design cannot be invalidated before expiry. However, business requirements demand immediate token revocation for user logout, password changes, and admin-initiated session termination. Without a revocation mechanism, compromised tokens remain valid until they naturally expire, posing a security risk.

## Decision

We implement a database-backed token blacklist using the `jti` (JWT ID) claim. Every issued token includes a unique `jti`. On logout or admin revocation, the `jti` is inserted into a `revoked_tokens` table with the token's expiry timestamp. The authentication middleware checks every incoming token's `jti` against this blacklist before granting access. A periodic Celery task cleans up expired entries to prevent unbounded table growth.

## Consequences

### Positive
- Enables immediate token revocation for logout, password reset, and admin actions
- Supports bulk revocation (all tokens for a user) via `revoke_all_user_tokens`
- Blacklist entries are self-cleaning via the periodic cleanup task
- Compatible with existing JWT infrastructure — no token format changes required

### Negative
- Adds a database lookup on every authenticated request, increasing latency slightly
- The `revoked_tokens` table must be highly available — database downtime affects all authentication
- Cleanup task must run reliably to prevent table bloat

### Neutral
- Token blacklist is a well-established pattern with predictable operational characteristics
- The performance overhead is mitigated by indexing on `jti` and keeping the table small via cleanup
