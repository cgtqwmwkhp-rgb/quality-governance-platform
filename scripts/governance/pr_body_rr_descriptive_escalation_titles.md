# Change Ledger (CL-RR-DESCRIPTIVE-ESCALATION-TITLES)

**Path claim:** `path11/rr-descriptive-escalation-titles`

## File allowlist (exclusive)

- `src/domain/services/audit_escalation_risk_title.py`
- `src/domain/services/audit_service.py`
- `src/api/routes/risk_register.py`
- `tests/unit/test_audit_escalation_risk_title.py`
- `tests/unit/test_audit_finding_risk_gates.py`
- `scripts/governance/pr_body_rr_descriptive_escalation_titles.md`

**Zero overlap** with parallel lanes: RiskProfile, RR-W4 import UI, Alembic, App.tsx, Planet Mark.

## 1) Summary

- **Feature / Change name:** Path11 — Descriptive titles for audit-escalated enterprise risks
- **User goal:** Risk Register rows show the audit finding title (or description preview) instead of opaque `Audit escalation: AUD-xxx / FND-xxx` labels; legacy rows can be backfilled per tenant.
- **In scope:** Title builder helper; forward-fix in `_ensure_risk_for_finding`; one-shot upgrade when linking existing generic-titled risks; `POST /risk-register/backfill-descriptive-titles` dry-run/commit; unit tests; Change Ledger
- **Out of scope:** RiskProfile.tsx; Alembic migration; FE subtitle (optional nice-to-have deferred); external import suggested-title prefix change
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| New audit escalations | Generic ref-based risk title | Finding title / description preview (+ optional ref suffix) |
| Re-link to existing generic risk | Title unchanged | One-time title upgrade to descriptive label |
| Ops backfill | Manual rename only | `POST /risk-register/backfill-descriptive-titles?commit=false\|true` |
| AUD/FND refs | Only in title | Remain in `linked_audits`, description, treatment text |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Forward-fix on create/link; optional tenant-scoped backfill (dry-run default)
- **Breaking changes:** None — titles become more descriptive; refs preserved in linkage fields
- **Rollback strategy:** Revert squash merge; re-run backfill not required for forward path

## 4) Acceptance Criteria (AC)

- [x] AC-01: New escalated risks prefer non-generic `suggested_title`, else `finding.title`, else description preview, else ref fallback
- [x] AC-02: Generic `Audit escalation:` / `Imported audit escalation:` patterns never used as sole human title when finding text exists
- [x] AC-03: Linking an existing generic-titled risk upgrades title once from finding
- [x] AC-04: AUD/FND refs remain in `linked_audits` / description — not stripped
- [x] AC-05: Backfill endpoint supports dry-run (default) and commit modes, permission-gated (`risk:update`)
- [x] AC-06: Unit tests cover title builder, upgrade-on-link, and backfill dry-run/commit

## 5) Testing Evidence

- [x] pytest — `tests/unit/test_audit_escalation_risk_title.py`, `tests/unit/test_audit_finding_risk_gates.py`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Nonconformity finding with title → new risk title matches finding (not ref string)
- [x] CUJ-02: Existing generic-titled risk re-linked → title upgraded from finding
- [x] CUJ-03: Backfill dry-run lists would-update rows; commit persists renames

## 7) Observability & Ops

- **Backfill:** `POST /api/v1/risk-register/backfill-descriptive-titles?commit=false` (dry-run) then `commit=true`
- **Playwright hooks:** N/A (BE-only)

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging: trigger backfill dry-run on UAT tenant; commit if preview OK

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [x] `pytest tests/unit/test_audit_escalation_risk_title.py tests/unit/test_audit_finding_risk_gates.py -q`
- [ ] Manual: escalate finding → Risk Register shows finding title
- [ ] Manual: backfill dry-run → commit on UAT tenant
