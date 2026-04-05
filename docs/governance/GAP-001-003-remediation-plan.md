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

## Post-production pillars — what was executed vs backlog

Each pillar is a **separate governance surface**: different users, different data paths, and different acceptance criteria. The tables below replace the former flat “optional follow-ups” list.

### Pillar I — Risk import triage (enterprise risk suggestions)

| Follow-up | Action executed | Robustness / controls |
|-----------|-----------------|------------------------|
| **Reject + notes in UI** | **Reject** opens a dialog with optional **Notes** (trimmed, max length enforced in UI). Non-empty notes are sent on `resolveSuggestionTriage`. **Accept** remains one-click. | While a triage request runs, triage controls are disabled; dismiss / escape on the reject dialog is blocked until the request finishes. **Success and failure** surface via toasts (i18n: `risk_register.import_triage_toast_*`). |
| **API parity** | `POST /risk-register/{id}/suggestion-triage` accepts `decision` and optional `notes`. | Server-side validation unchanged; client shows operator feedback on failure. |

**Primary evidence:** `frontend/src/pages/RiskRegister.tsx`, `src/api/routes/risk_register.py`.

### Pillar II — CAPA vs risk triage (governance bridge)

| Follow-up | Action executed | Robustness / controls |
|-----------|-----------------|------------------------|
| **Clarify dual path (not a second CAPA triage)** | **Documented in product copy**, not rebuilt as a second triage workflow. Actions page **playbook** explains that CAPA from the same import stays in **Actions**; only **register suggestions** use Import triage. | Welsh parity for new `actions.*` strings in `cy.json`. |
| **Operator wayfinding** | Actions: links to audit run execute, import review, and **Risk Register** `?triage=import`. Risk Register: URL sync for `?triage=import`. | **Import review → reconciliation:** “Governance hand-off after promotion” panel when `capa_actions` or `enterprise_risks` is non-zero, with shortcuts to audit-sourced actions and import risk triage. |
| **API traceability** | `audit_run_id` on action list/detail responses; owner email hydration for list rows. | Unit test: `tests/unit/test_actions_audit_finding.py` (provenance + `audit_run_id`). |

**Primary evidence:** `frontend/src/pages/Actions.tsx`, `frontend/src/pages/AuditImportReview.tsx`, `src/api/routes/actions.py`.

### Pillar III — Deeper GAP-001 (explicit backlog)

| Item | Status | Notes |
|------|--------|--------|
| Auto `ComplianceEvidenceLink` on promote | Backlog | Recorded here; not in the delivered slice. |
| UVDB / Planet Mark matrix seed data | Backlog | Recorded here; not in the delivered slice. |
| Optional **pending** CAPA + triage UI (symmetry with risk triage) | Backlog | Product decision; CAPA remains live-on-promote today. |

---

## Enhancement review — Round 1 (pillar completeness)

**Scope:** Pillar I + Pillar II only (Pillar III remains backlog by design).

| Pillar | Finding | Disposition |
|--------|---------|------------|
| **I** | Reject path must not lose operator feedback on network/API failure | **Addressed:** error toast + existing loading/disable behaviour. |
| **I** | Success path should confirm accept vs reject for audit trail in the UI session | **Addressed:** distinct success toasts per decision. |
| **II** | Operators may not read Actions playbook before triaging risks | **Addressed:** reconciliation **governance hand-off** panel on import review after promotion. |
| **II** | i18n drift (Cymraeg) on new governance strings | **Addressed:** `cy.json` keys aligned to new `actions.*` copy. |

---

## Enhancement review — Round 2 (robustness / Fortune 500 bar)

| Pillar | Finding | Disposition |
|--------|---------|------------|
| **I** | Toasts must be translatable and consistent with the rest of the app | **Addressed:** `risk_register.import_triage_toast_*` in `en.json` / `cy.json`; `useTranslation` in `RiskRegister`. |
| **II** | Deep links should prefer server-provided `view_links.actions` when present | **Addressed:** hand-off **Open audit-sourced actions** uses `reconciliation.view_links.actions` with fallback to `/actions?sourceType=audit_finding`. |
| **II** | Avoid duplicating a full second triage workflow | **Accepted:** single triage workflow for **enterprise risks** only; CAPA remains authoritative in Actions. |

**Round 2 conclusion:** Pillar I and Pillar II are **complete** for this release; Pillar III stays **out of scope** (documented backlog).

---

## Execution action plan (locked — implemented in branch)

| Step | Deliverable | Verification |
|------|-------------|--------------|
| 1 | Import triage operator feedback (toasts + i18n) | Manual: accept/reject and reject+notes; force API error → error toast. |
| 2 | Import review governance hand-off panel | Manual: reconciliation with non-zero capa or enterprise risk counts → panel visible; buttons navigate correctly. |
| 3 | Cymraeg parity for governance `actions.*` keys | `cy.json` key parity with `en.json` for those strings. |
| 4 | Documentation (this file) | Reviewer can trace pillar → code → test. |
| 5 | CI + PR merge + staging + production | `make pr-ready`; green checks; governed `workflow_dispatch` production promotion per runbook. |

---

## References

- `src/domain/services/iso_cross_mapping_service.py`
- `src/domain/services/audit_service.py` — `_ensure_risk_for_finding`
- `src/domain/services/external_audit_import_service.py` — promotion
- `src/api/routes/risk_register.py`
- `frontend/src/pages/AuditImportReview.tsx`, `RiskRegister.tsx`, `ComplianceEvidence.tsx`
