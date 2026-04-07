# Test Factory Registry

**Status**: Current  
**Date**: 2026-04-07  
**Source file**: `tests/factories/core.py`  
**Assessed by**: World-Class Scorecard 2026-04-07 (EG-07 remediation)

---

## Summary

| Metric | Value |
|--------|-------|
| Total factory classes | 18 |
| Factory base | `factory.Factory` (factory-boy) |
| Source file | `tests/factories/core.py` |
| Prior claimed count | 15–17 (under-counted in scorecard 2026-04-03) |
| Confirmed count | **18** (verified 2026-04-07) |

---

## Factory Inventory

| # | Factory Class | Domain Entity |
|---|---------------|---------------|
| 1 | `TenantFactory` | Multi-tenancy / tenant isolation |
| 2 | `UserFactory` | User accounts |
| 3 | `IncidentFactory` | Incident management |
| 4 | `IncidentActionFactory` | Incident actions |
| 5 | `ComplaintFactory` | Complaints |
| 6 | `NearMissFactory` | Near-miss events |
| 7 | `AuditTemplateFactory` | Audit templates |
| 8 | `CAPAActionFactory` | Corrective and preventive actions |
| 9 | `RiskFactory` | Risk register entries |
| 10 | `PolicyFactory` | Policy library |
| 11 | `RTAFactory` | Road traffic collisions |
| 12 | `RTAActionFactory` | RTA follow-up actions |
| 13 | `AuditRunFactory` | Audit runs |
| 14 | `AuditFindingFactory` | Audit findings |
| 15 | `InvestigationFactory` | Investigations |
| 16 | `EnterpriseRiskFactory` | Enterprise risk register |
| 17 | `EvidenceAssetFactory` | Evidence assets |
| 18 | `ExternalAuditImportJobFactory` | External audit imports |

---

## Coverage Gaps

The following domain areas currently lack factory coverage and should be considered for future test data uplift:

- Push notification subscriptions (`PushSubscription`)
- GDPR data subject requests
- ISO 27001 / ISMS controls
- IMS dashboard aggregations (derived, so likely covered by underlying factories)
- Digital signatures (`DigitalSignature`)

---

## Update Cadence

This registry should be updated whenever a new factory class is added to `tests/factories/core.py`. It feeds into the D16 (Test Data & Fixtures) dimension of the World-Class Scorecard.
