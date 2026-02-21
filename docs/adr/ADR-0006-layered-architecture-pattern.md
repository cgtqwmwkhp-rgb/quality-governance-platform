# ADR-0006: Layered Architecture — api/domain/infrastructure/core Separation

**Status:** Accepted
**Date:** 2026-02-21
**Authors:** Platform Engineering Team

## Context

The Quality Governance Platform manages compliance across multiple ISO standards (9001, 14001, 27001, 45001), resulting in a complex codebase with dozens of modules. Without clear architectural boundaries, business logic leaked into route handlers, infrastructure concerns mixed with domain logic, and circular dependencies emerged between modules. A principled separation of concerns is essential for long-term maintainability and testability.

## Decision

We adopt a four-layer architecture with strict dependency direction: `api → domain → infrastructure → core`. The **api** layer handles HTTP concerns (routing, serialization, authentication). The **domain** layer contains business logic, service classes, and domain models. The **infrastructure** layer manages external integrations (database, Redis, email, blob storage). The **core** layer provides shared utilities, configuration, and base classes used by all other layers.

## Consequences

### Positive
- Clear separation of concerns makes the codebase easier to navigate and reason about
- Each layer can be tested in isolation with appropriate mocking boundaries
- Strict dependency direction prevents circular imports and tangled coupling
- New developers can orient quickly by understanding the four-layer contract

### Negative
- Additional boilerplate when simple operations must flow through multiple layers
- Refactoring existing code to conform to the layered pattern requires upfront investment
- Some pragmatic shortcuts (e.g., direct DB access from routes) are no longer acceptable

### Neutral
- Layer boundaries are enforced by convention and code review, not by tooling
- The pattern is well-understood in the industry, reducing onboarding friction
