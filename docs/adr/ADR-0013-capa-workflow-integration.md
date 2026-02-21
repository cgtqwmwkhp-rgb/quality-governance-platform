# ADR-0013: CAPA Module with Audit Trail Integration

**Status:** Accepted
**Date:** 2026-02-21
**Authors:** Platform Engineering Team

## Context

Corrective and Preventive Actions (CAPA) are a core requirement of ISO 9001, ISO 14001, and ISO 45001 quality management systems. CAPAs must follow a defined lifecycle (identification, investigation, action planning, implementation, verification, closure) with full traceability of who made each transition and when. Regulatory auditors expect evidence of controlled CAPA processes with tamper-evident records.

## Decision

We implement a CAPA module with a state machine governing lifecycle transitions. Valid states are: `open`, `investigation`, `action_planned`, `in_progress`, `verification`, `closed`, and `rejected`. Each state transition is validated against an allowed-transitions map to prevent invalid jumps (e.g., directly from `open` to `closed`). Every state change is automatically recorded in the audit trail with the user, timestamp, previous state, new state, and optional justification. The audit trail uses hash chaining for tamper evidence.

## Consequences

### Positive
- Full lifecycle traceability satisfies ISO audit requirements for CAPA processes
- State machine prevents invalid transitions, enforcing process discipline
- Hash-chained audit trail provides tamper-evident evidence for regulatory auditors
- Integration with existing audit trail infrastructure eliminates duplicate logging systems

### Negative
- State machine rigidity may frustrate users who want to skip steps in urgent situations
- Audit trail entries accumulate over time, requiring archival or retention policies
- Hash chain verification adds computational overhead to audit trail queries

### Neutral
- CAPA states and transitions are configurable but changes require careful migration planning
- The module follows the same layered architecture pattern (ADR-0006) as other domain modules
- CAPA records are tenant-scoped following the multi-tenant isolation model (ADR-0012)
