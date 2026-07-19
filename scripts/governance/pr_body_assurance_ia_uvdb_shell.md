# Change Ledger (CL-ASSURANCE-IA-UVDB-SHELL)

## File allowlist (exclusive)

- `frontend/src/pages/UVDBAudits.tsx`
- `frontend/src/pages/uvdbHelpers.ts`
- `frontend/src/pages/__tests__/UVDBAudits.test.tsx`
- `frontend/src/pages/__tests__/uvdbHelpers.test.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_assurance_ia_uvdb_shell.md`

**Zero overlap** with parallel lanes: Planet Mark, Customer Audits, Import Review, ISO specialist shell, Layout, App, client.ts, backend routes.

## 1) Summary

- **Feature / Change name:** Assurance IA Wave 3 — UVDB Achilles shell (Planet Mark IA clone)
- **User goal:** Operators on `/uvdb` get Audits-style pill section toggles synced to `?section=` — **Scores · Protocol · Audits · Mapping · Export** — with per-section honesty; export stays disabled until the protocol pack route is wired (no fake downloads).
- **In scope:** UVDB page shell refactor; `uvdbHelpers`; vitest; minimal `uvdb.shell.*` i18n
- **Out of scope:** Customer Audits IA; Import Review; ISO specialist shell (separate PR); backend export pack route; shared cross-page shell component extraction
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Page IA | 4 in-page tabs (`dashboard`, `protocol`, `audits`, `mapping`) | 5 Planet Mark-style sections: `scores`, `protocol`, `audits`, `mapping`, `export` |
| Section nav | Border-bottom tab row | Audits-style `bg-surface` pill toggle + URL `?section=` sync + section `<select>` |
| Export | Header disabled button + honesty caption | Dedicated export section with disabled CTA + honesty copy |
| Deep links | `?auditRef=` forced audits tab via local state | `?auditRef=` opens `audits` when `section` absent; `?section=export` permalinks export |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** FE-only shell; existing UVDB APIs unchanged
- **Breaking changes:** None on route; legacy in-page tab state removed in favour of URL `section` param (default `scores`)
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Five sections — scores, protocol, audits, mapping, export — with Planet Mark-style pill toggle
- [x] AC-02: URL `?section=` sync; default scores; `?auditRef=` opens audits when section omitted
- [x] AC-03: Export section keeps protocol pack honesty — disabled control, no fabricated download
- [x] AC-04: Existing scores / protocol / audits / mapping content preserved under new section ids
- [x] AC-05: Vitest covers shell tabs, export honesty, helpers, existing UVDB flows

## 5) Testing Evidence

- [x] Vitest — `UVDBAudits.test.tsx`, `uvdbHelpers.test.ts`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Tenant with UVDB audits — Scores section shows live dashboard KPIs
- [x] CUJ-02: Export tab — honest disabled export, no broken download affordance
- [x] CUJ-03: Import recovery — `?auditRef=` deep-link still opens Audit History section

## 7) Observability & Ops

- **Playwright hooks:** `uvdb-section-scores`, `uvdb-section-protocol`, `uvdb-section-audits`, `uvdb-section-mapping`, `uvdb-section-export`, `uvdb-export-protocol-honesty`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (parent coordinates)
3. Staging tip smoke `/uvdb` and `/uvdb?section=export`

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Follow-ons (out of scope for this PR)

| Slice | Scope | Rationale |
|-------|-------|-----------|
| **ISO shell** | Clone same IA onto ISO specialist home | Separate surface + mapping UX — recommend separate PR |
| **UVDB export pack** | Wire backend pack route + enable download | Requires API route |
| **Shared shell component** | Extract pill toggle + `?section=` helper | Only if third assurance page adopts same pattern |

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [x] `cd frontend && npx vitest run src/pages/__tests__/UVDBAudits.test.tsx src/pages/__tests__/uvdbHelpers.test.ts`
- [ ] Manual: `/uvdb` — verify five sections, pill toggle, export honesty; `/uvdb?section=export`; `/uvdb?auditRef=…` opens audits
