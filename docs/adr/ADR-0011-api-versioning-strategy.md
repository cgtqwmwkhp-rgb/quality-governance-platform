# ADR-0011: API Versioning Strategy

## Status
Accepted

## Date
2026-04-03

## Context
The platform exposes REST APIs consumed by the SPA frontend and potential external integrations. We need a versioning strategy that allows non-breaking evolution while supporting breaking changes when necessary.

## Decision
We adopt URL-prefix versioning (`/api/v1/`, `/api/v2/`) for all public API endpoints. The `api-path-drift` CI gate enforces that all test paths include the version prefix. New major versions are introduced only for breaking changes and old versions are maintained for a minimum of 6 months after deprecation notice.

## Consequences
- All routes must be registered under `/api/v1/` prefix
- The `api-path-drift` CI job validates compliance
- Breaking changes require a new version prefix and migration guide
- Non-breaking additions (new fields, new endpoints) are added to the current version
