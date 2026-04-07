# ADR-0015: Centralised Error Code Catalog with CI Enforcement

**Status**: Accepted  
**Date**: 2026-04-07  
**Decision Makers**: Platform Team  

## Context

Prior to this decision, error codes were scattered across multiple files and sometimes as bare strings in exception raise sites. This caused:

1. Inconsistent error codes in API responses — consumers could not reliably branch on `error.code`
2. No automated verification that defined error codes are actually exercised in tests
3. Dead error codes (defined but never raised) accumulating silently
4. No single document describing the full error vocabulary

The `src.domain.exceptions` hierarchy and `src.api.middleware.error_handler` provided partial structure, but the catalog was not enforced.

## Decision

We establish **`src/domain/error_codes.py`** as the single source of truth for all error codes. The ErrorCode enum is imported by both the domain layer (`exceptions.py`) and the API layer (`schemas/error_codes.py`).

A new CI gate — `error-code-coverage` — runs `scripts/validate_error_code_coverage.py` on every push and PR. The gate:

1. Extracts all `ErrorCode` members from the enum
2. Scans `tests/` for references to each code (enum member name or string value)
3. Verifies each code is either directly referenced in tests OR is classified as `EXEMPT` with a documented reason
4. Hard-fails if any code is dead (defined but not raised in `src/`) or if the count of indirectly-tested codes exceeds a documented threshold

## Consequences

**Positive:**
- API consumers can enumerate all possible error codes from a single file
- No dead error codes can accumulate silently past CI
- The error code catalog is always in sync with test coverage

**Negative:**
- New error codes require an accompanying test (or explicit exemption)
- Exemptions must be documented in `EXEMPT_CODES` with a justification

## Alternatives Considered

- Generate error codes from OpenAPI spec: rejected — spec is generated from code, not the reverse
- Use bare strings in raise sites: rejected — inconsistent, unverifiable, not refactor-safe
