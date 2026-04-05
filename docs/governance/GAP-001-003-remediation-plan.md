# GAP-001 — GAP-003 Remediation Plan

This document records **two independent revisions** of the gap analysis and remediation approach, then tracks **implementation completion**.

---

## Revision 1 — Initial identification and draft actions

### Gap identification

| ID | Gap | Current state (evidence) |
|----|-----|---------------------------|
| **GAP-001** | Richer cross-standard evidence UX (bi/multi-way) | `ISOCrossMappingService` is text-regex only (`iso_cross_mapping_service.py`). `ExternalAuditAnalysisService` merges regex + clause auto-tag into `mapped_standards` / draft JSON. `AuditImportReview.tsx` shows flat badges only. `ComplianceEvidence.tsx` loads `crossStandardMappingsApi` per clause; **no deep link** from import review. `UVDBAudits.tsx` has ISO matrix + API. |
| **GAP-002** | Risk register triage for import-sourced suggestions | `_ensure_risk_for_finding` in `audit_service.py` **immediately** persists `EnterpriseRisk` (e.g. `status="open"`, `is_escalated=True`). No `pending` / accept-reject workflow. |
| **GAP-003** | Planet Mark naming consistency | Repo uses **Planet Mark** in UI/API; no `Planmark` hits. Risk is **future drift** and **external comms**; needs SSOT note. |

### Draft action plan (R1)

1. **GAP-003:** Add glossary / style note; optional CI grep for forbidden variants.
2. **GAP-002:** Add nullable `suggestion_triage_status` on `risks_v2`; import promotion sets `pending`; API + UI to accept/reject; exclude `pending` from default list, summary, heatmap.
3. **GAP-001:** Enrich import review with cross-standard table + links to Compliance; support `?clause=` on `/compliance`; optionally extend `ISOCrossMappingService` documentation/patterns.

### R1 risks

- Heatmap/summary drift if `pending` risks not excluded everywhere.
- Breaking change if existing tenants expect import risks to appear as fully escalated immediately → mitigate with **clear triage tab** and **accept** restoring prior escalation behaviour.

---

## Revision 2 — Refined scope, acceptance criteria, execution order

### Refined identification (unchanged facts, tighter scope)

| ID | In scope for this delivery | Explicitly out of scope |
|----|----------------------------|-------------------------|
| **GAP-001** | Import-review **Cross-standard evidence** panel with confidence/basis and **Open in Compliance** links; Compliance page reads **`?clause=`** (clause number) to focus clause. | New cross-map seed data for Planet Mark; IMS dashboard redesign; automated `ComplianceEvidenceLink` backfill jobs. |
| **GAP-002** | **Only** risks created via **external audit import promotion** enter `suggestion_triage_status=pending`. All other creation paths unchanged. `POST /risk-register/{id}/suggestion-triage`. **Risk Register** subview **Import triage**. | CAPA deferral; email notifications; bulk triage. |
| **GAP-003** | New **`docs/ux/glossary-trademarks.md`** with canonical **Planet Mark** wording; reference from `information-architecture.md`. | Trademark symbol (®) without legal sign-off — not added. |

### Execution order (R2)

1. **GAP-003** (docs) — zero runtime risk.
2. **GAP-002** (migration → service → API → UI) — behaviour change; must update summary + heatmap + list filters consistently.
3. **GAP-001** (UX + query param) — depends on stable routes only.

### Acceptance criteria (R2)

| AC | Criterion |
|----|-----------|
| AC-G3-01 | Glossary file exists and states canonical **Planet Mark** product name. |
| AC-G2-01 | Alembic adds `suggestion_triage_status` (nullable) on `risks_v2`. |
| AC-G2-02 | Promoting an external import finding creates risks with `pending` when severity triggers risk creation. |
| AC-G2-03 | Default risk list / summary / heatmap **exclude** `pending`. |
| AC-G2-04 | `suggestion_triage=pending` lists only pending; resolve endpoint sets `accepted` or `rejected` (+ closed on reject). |
| AC-G1-01 | Import review shows structured cross-standard section with link to `/compliance?clause=…`. |
| AC-G1-02 | Compliance view applies `clause` query to selection when data loads. |

### Implementation status (post-delivery)

| Item | Status |
|------|--------|
| Revision 1 documented | Done |
| Revision 2 documented | Done |
| GAP-003 implementation | Done (see glossary + IA link) |
| GAP-002 implementation | Done (migration, `audit_service`, `risk_register`, `risk_service`, FE) |
| GAP-001 implementation | Done (`AuditImportReview`, `ComplianceEvidence`) |

---

## References

- `src/domain/services/iso_cross_mapping_service.py`
- `src/domain/services/audit_service.py` — `_ensure_risk_for_finding`
- `src/domain/services/external_audit_import_service.py` — promotion
- `src/api/routes/risk_register.py`
- `frontend/src/pages/AuditImportReview.tsx`, `RiskRegister.tsx`, `ComplianceEvidence.tsx`
