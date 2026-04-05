# CUJ review — Import triage, CAPA bridge, import reconciliation (2026-04-05)

This evidence pack answers: **Is everything captured, wired, and flowing?** It uses **four intensive review passes** over the same **four critical user journeys (CUJs)**. It records **gaps**, **contract/schema pointers**, and a **manual UAT** script suitable for staging or production smoke.

---

## 1. Critical user journeys (CUJ)

| ID | Journey | Happy path | Failure / edge path |
|----|---------|------------|---------------------|
| **CUJ-01** | **Accept import risk** | External audit import promotes finding → `EnterpriseRisk` with `suggestion_triage_status=pending` → user opens **Risk Register → Import triage** → **Accept** → risk becomes `accepted`, escalated, visible in default register views per `risk_register` + `risk_service` filters. | API 400 if not `pending`; toast on network error; buttons disabled while submitting. |
| **CUJ-02** | **Reject import risk + notes** | User clicks **Reject** → dialog → optional notes (max **2000** chars, matches API `Field(max_length=2000)`) → **Confirm** → `rejected`, `status=closed`, notes appended to `review_notes`; dialog blocks dismiss/escape while `triageSubmitting`. | Same error handling as CUJ-01; on API error, dialog remains open (errors are caught inside `resolveImportTriage`, not rethrown). |
| **CUJ-03** | **CAPA vs triage clarity** | User on **Actions** sees audit playbook copy + links to execute / import review / **Risk Register `?triage=import`**. After promotion, **Audit import review → reconciliation** shows **Governance hand-off** when `materialized.capa_actions` or `materialized.enterprise_risks` is non-zero, with shortcuts to Actions (prefers `view_links.actions`) and import triage. | If reconciliation counts are zero, hand-off panel hidden (by design). |
| **CUJ-04** | **Audit-sourced action traceability** | Actions list/detail include `audit_run_id` when provenance allows; links to `/audits/{id}/execute` and `/audits/{id}/import-review`. | Missing `audit_run_id` when provenance JSON lacks it — links hidden (defensive UI). |

---

## 2. Intensive review — pass 1 (database & domain wiring)

**Verdict:** **Wired end-to-end** for import-sourced pending risks.

| Topic | Evidence | Notes |
|-------|-----------|--------|
| **Column** | `EnterpriseRisk.suggestion_triage_status` on `risks_v2` | Nullable `String(32)`; index in Alembic `20260406_add_risk_suggestion_triage_status.py`. |
| **Promotion → pending** | `external_audit_import_service` sets `_external_import_risk_triage_pending` on finding data; `audit_service._ensure_risk_for_finding(..., external_import_triage_pending=True)` sets `suggestion_triage_status="pending"`, `is_escalated=False`, triage-oriented `treatment_plan` / `escalation_reason`. | Non-import paths use `triage_flag=None` (legacy immediate escalation behaviour preserved). |
| **Visibility** | `risk_register.list` default filter hides `pending` via `_register_visibility_clause()`; `suggestion_triage=pending` shows queue only. | Aligns with heatmap/summary exclusions in `risk_service` (pending not treated as live register). |
| **Resolve** | `POST /api/v1/risk-register/{risk_id}/suggestion-triage` | Accept: `accepted` + `is_escalated=True`; Reject: `rejected` + `closed` + `review_notes` merge; cache invalidation for tenant. |
| **Tests added (gap closure)** | `tests/integration/test_risk_register_suggestion_triage.py` | Covers accept, reject+notes, double-resolve 400 envelope, pending list filter before/after. |

**Gap (remaining):** No automated E2E in browser for triage dialog (Vitest/Playwright not extended in this pass); rely on manual UAT below.

---

## 3. Intensive review — pass 2 (API & contracts)

**Verdict:** **Runtime API is consistent**; **published OpenAPI artifact is incomplete** for this surface.

| Topic | Evidence | Notes |
|-------|-----------|--------|
| **Suggestion triage** | `SuggestionTriageResolve` Pydantic model; `resolve_suggestion_triage` in `src/api/routes/risk_register.py` | Structured errors use platform envelope (`error.message`), not plain `detail` string — clients must read both shapes (frontend axios layer typically normalizes). |
| **List contract** | `GET /api/v1/risk-register/?suggestion_triage=pending` returns `{ total, page, page_size, items: [...] }` with `suggestion_triage_status` on each item. | Matches `riskRegisterApi.list` in `frontend/src/api/client.ts`. |
| **Actions** | `ActionResponse.audit_run_id` in `src/api/routes/actions.py` | Hydration from finding provenance + run lookup where implemented. |
| **OpenAPI / contract SSOT** | `docs/contracts/openapi.json` | **Gap:** No `/api/v1/risk-register/...` paths located in this bundle (enterprise register lives outside the captured contract file). **Recommendation:** Regenerate/publish OpenAPI to include `risk-register` + `suggestion-triage` + `audit_run_id` on action schemas, or scope a dedicated “enterprise register” contract file and gate it in CI. |

---

## 4. Intensive review — pass 3 (frontend UX & flow)

**Verdict:** **Best-in-class for clarity** on dual-path messaging. **Assurance scope is English-only** (Welsh locale files may exist in-repo but are not a review or UAT gate).

| Area | Status | Notes |
|------|--------|--------|
| **Import triage UX** | **Strong** | Mode toggle + URL sync `?triage=import`; helper copy explains CAPA vs register triage; reject dialog with `maxLength={2000}`; loading disables actions; Radix dismiss guarded while submitting. |
| **Toasts** | **Strong** | Success/error for triage via `toast` + `risk_register.import_triage_toast_*` in `en.json` (English-speaking product). |
| **Actions bridge** | **Strong** | Playbook + deep links; `audit_run_id` guarded links. |
| **Import review hand-off** | **Strong** | Reconciliation panel + navigation to Actions / import triage. |
| **Register chrome** | **Low (optional)** | Page title, mode labels, and helper copy are mostly **inline English**; triage toasts use `useTranslation` + `en.json`. For an English-only product this is acceptable; centralising register strings in `en.json` remains an optional consistency tidy-up. |
| **Reconciliation `view_links`** | **OK** | Top-level reconciliation `view_links.actions` is generic `/actions?sourceType=audit_finding`; per-draft rows include `sourceId` — acceptable; hand-off uses top-level link with fallback. |

---

## 5. Intensive review — pass 4 (quality, security, operations)

**Verdict:** **CI-quality improved** for triage; **container scan debt** remains visible on some main runs.

| Topic | Evidence | Notes |
|-------|-----------|--------|
| **Unit / integration** | `test_enterprise_risk_triage.py` (column exists) + **new** `test_risk_register_suggestion_triage.py` | Closes the “no API-level triage test” gap. |
| **Security Scan / Trivy** | Documented in `release_signoff.json` for PR #436 promotion | Treat as **image hygiene backlog**, not UX regression. |
| **UAT (manual)** | Use checklist below on **staging** after deploy | Record screenshot or ticket IDs in your CAB pack if required. |

---

## 6. Wiring matrix (quick reference)

| Capability | Backend | DB | Frontend | Tests |
|------------|---------|-----|----------|--------|
| Pending import risk | `audit_service._ensure_risk_for_finding` | `suggestion_triage_status` | Import triage list | Integration |
| Resolve accept/reject | `risk_register.resolve_suggestion_triage` | column + `review_notes` / `escalation_reason` | `resolveSuggestionTriage` + dialog | Integration |
| Hide pending from default list | `list_risks` filter + `risk_service` | same column | `registerMode` + API `suggestion_triage` | Integration |
| CAPA messaging | N/A (CAPA always live) | `capa_actions` | `Actions.tsx` + `AuditImportReview` | Manual |
| `audit_run_id` | `actions.py` | provenance on action/finding | `Actions.tsx` | `test_actions_audit_finding.py` |

---

## 7. Manual UAT script (staging or production)

1. **CUJ-01:** Create or use tenant with a promoted external import that materialized a **pending** enterprise risk → open `/risk-register?triage=import` → **Accept** → confirm success toast → risk disappears from triage queue → appears under default register behaviour (not pending).
2. **CUJ-02:** Repeat with **Reject** → enter notes → confirm → error toast if API blocked; on success, risk closed, toast shown, dialog closes.
3. **CUJ-03:** Open **Actions** with audit-sourced rows → read playbook → follow **Risk import triage** link → land in import triage mode. Open import review reconciliation with non-zero capa/risk counts → verify **Governance hand-off** panel and both buttons.
4. **CUJ-04:** From Actions, open **audit run** and **import review** links where `audit_run_id` present; confirm no broken routes.

---

## 8. Errors & discrepancies captured

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| E-01 | Low | Error JSON uses `error.message` not always `detail` | Integration test updated to accept both; frontend uses shared API client. |
| E-02 | Medium | `docs/contracts/openapi.json` missing enterprise `risk-register` paths | Track as contract debt; regenerate OpenAPI or extend gate. |
| E-03 | — | *(Retired.)* English-only product; no Welsh/locale gate. |
| E-04 | Low | Trivy / container gate may fail on `Security Scan` workflow while `CI` is green | Already noted in release signoff; remediate under security chapter. |

---

## 9. Codebase inventory (primary touchpoints)

- `src/api/routes/risk_register.py` — list filter, `resolve_suggestion_triage`
- `src/domain/services/audit_service.py` — `_ensure_risk_for_finding`, triage pending branch
- `src/domain/services/external_audit_import_service.py` — promotion flag, reconciliation `materialized` / `view_links`
- `src/domain/services/risk_service.py` — heatmap/summary pending exclusion
- `src/domain/models/risk_register.py` — `EnterpriseRisk.suggestion_triage_status`
- `alembic/versions/20260406_add_risk_suggestion_triage_status.py` — migration
- `frontend/src/pages/RiskRegister.tsx` — triage UI, dialog, toasts
- `frontend/src/pages/Actions.tsx` — playbook, links, `audit_run_id`
- `frontend/src/pages/AuditImportReview.tsx` — governance hand-off panel
- `frontend/src/api/client.ts` — `resolveSuggestionTriage`, list query param
- `frontend/src/i18n/locales/en.json` — triage toasts + actions playbook keys (English assurance)
- `tests/integration/test_risk_register_suggestion_triage.py` — **new**
- `tests/unit/test_actions_audit_finding.py` — `audit_run_id` provenance
- `docs/governance/GAP-001-003-remediation-plan.md` — pillar narrative

---

## 10. Sign-off (reviewer attestation)

| Review pass | Completed | Reviewer action |
|-------------|-----------|-----------------|
| Pass 1 — Data / DB / domain | Yes | Trace promotion → pending → resolve |
| Pass 2 — API / contracts | Yes | Confirmed runtime + flagged OpenAPI gap |
| Pass 3 — Frontend / UX | Yes | Confirmed flows; English-only scope |
| Pass 4 — Quality / ops | Yes | Added integration tests + UAT script |

**Automated:** `python3.11 -m pytest tests/integration/test_risk_register_suggestion_triage.py` — 4 passed (local 2026-04-05).

**Manual UAT:** Required for “best in class” attestation in regulated environments; execute §7 on staging and attach evidence to your change record.
