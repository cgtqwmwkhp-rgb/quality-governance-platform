# Change Ledger (CL-EMP-07-INDUCTION-SKILLS)

**Path claim:** `path11/emp-07-induction-skills`

## File allowlist (exclusive)

- `frontend/src/pages/workforce/InductionCreate.tsx`
- `frontend/src/pages/workforce/CompetencyDashboard.tsx`
- `frontend/src/pages/workforce/EngineerProfile.tsx`
- `frontend/src/pages/workforce/__tests__/InductionCreate.test.tsx`
- `frontend/src/pages/workforce/__tests__/CompetencyDashboard.test.tsx`
- `frontend/src/pages/workforce/__tests__/EngineerProfile.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_emp_07_induction_skills.md`

**Zero overlap** with parallel lanes: PlanetMark*, IMS*, Documents*, Layout/App/client.ts spines, `api/__init__.py`, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 EMP-07 — Induction picker + skills matrix / role_key allocate honesty
- **User goal:** Induction create uses the same active role-aware employee picker as assessments; skills matrix states it is asset-type status (not role allocate); employee profile allocates mandatory requirements by role_key ≈ job_title.
- **In scope:** InductionCreate picker parity; CompetencyDashboard honesty; EngineerProfile role_key matching + filtered list; vitest; i18n
- **Out of scope:** Backend schema changes; Layout/App/client.ts; competency allocate API redesign
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| Induction engineer select | Raw employee_number list, page_size 200 | Active roster picker + role-aware labels + empty honesty |
| Skills matrix | Implied role allocate | Honesty: cells are asset-type competency status |
| Requirements coverage | Exact role_key === job_title; list showed all mandatory | ILIKE-style contains match; list filtered to applicable + role label |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** FE-only; uses existing competencyRequirements API
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Induction picker uses ACTIVE_EMPLOYEES_LIST_PARAMS + role-aware labels
- [x] AC-02: Empty roster honesty on induction create
- [x] AC-03: Skills matrix honesty banner
- [x] AC-04: role_key ≈ job_title allocate + filtered requirements list
- [x] AC-05: Vitest coverage
- [x] AC-06: en + cy flat keys

## 5) Testing Evidence

- [x] Vitest — InductionCreate, CompetencyDashboard, EngineerProfile
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: New induction → active employee picker
- [x] CUJ-02: Employee profile → role-scoped requirements only

## 7) Observability & Ops

- **Playwright hooks:** `induction-create-employees-empty`, `competency-skills-matrix-honesty`, `requirements-role-key-honesty`

## 8) Checklist id

**EMP-07** (living tracker)
