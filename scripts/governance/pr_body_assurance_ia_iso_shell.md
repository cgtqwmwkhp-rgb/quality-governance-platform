# Change Ledger (CL-ASSURANCE-IA-ISO-SHELL)

## File allowlist (exclusive)

- `frontend/src/pages/ComplianceEvidence.tsx`
- `frontend/src/pages/complianceEvidenceHelpers.ts`
- `frontend/src/pages/IMSDashboard.tsx`
- `frontend/src/pages/imsDashboardHelpers.ts`
- `frontend/src/pages/__tests__/ComplianceEvidence.test.tsx`
- `frontend/src/pages/__tests__/complianceEvidenceHelpers.test.ts`
- `frontend/src/pages/__tests__/IMSDashboard.test.tsx`
- `frontend/src/pages/__tests__/imsDashboardHelpers.test.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_assurance_ia_iso_shell.md`

**Zero overlap** with UVDB (PR #1161 / `feat/assurance-ia-uvdb`), Customer Audits, Import Review, campaign files, backend.

## 1) Summary

- **Feature / Change name:** Assurance IA follow-on — ISO Compliance + IMS shell alignment (Planet Mark pattern)
- **User goal:** Operators on `/compliance` and `/ims` get Audits/Planet Mark-style pill navigation with URL `?section=` sync; IMS keeps compliance hub chips + external destinations.
- **In scope:** Section helpers, pill + filter-bar IA, vitest, `compliance.evidence.shell.*` + `ims.shell.*` i18n
- **Out of scope:** UVDBAudits, backend, Layout/App routing changes, new npm deps
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| `/compliance` section nav | Local `viewMode` state, `bg-secondary` Button tabs | URL `?section=` sync + Planet Mark `bg-surface` pill toggle + header `<select>` |
| `/compliance` deep links | `?standard=` / `?clause=` only | Same + `?section=evidence\|gaps\|imported` (default `clauses` omits param) |
| `/ims` section nav | Local `activeTab` state, border-bottom Button row | URL `?section=` sync + pill toggle + header `<select>` |
| `/ims` hub | Destination cards unchanged | ISMS chip sets `?section=isms` instead of local tab state |
| Honesty / empty states | Preserved | Unchanged copy and empty panels |

## 3) Section IDs

### ISO Compliance (`/compliance`)

| Section ID | Default? | i18n key |
|------------|----------|----------|
| `clauses` | yes | `compliance.evidence.shell.section.clauses` |
| `evidence` | | `compliance.evidence.shell.section.evidence` |
| `gaps` | | `compliance.evidence.shell.section.gaps` |
| `imported` | | `compliance.evidence.shell.section.imported` |

### IMS (`/ims`)

| Section ID | Default? | i18n key |
|------------|----------|----------|
| `overview` | yes | `ims.shell.section.overview` |
| `mapping` | | `ims.shell.section.mapping` |
| `audit` | | `ims.shell.section.audit` |
| `review` | | `ims.shell.section.review` |
| `isms` | | `ims.shell.section.isms` |

## 4) Compatibility & Data Safety

- **Compatibility strategy:** FE-only shell; existing APIs unchanged
- **Breaking changes:** None (routes unchanged); bookmarkable section URLs added
- **Rollback strategy:** Revert squash merge

## 5) Acceptance Criteria (AC)

- [x] AC-01: `/compliance` — four sections with pill + filter-bar + `?section=` sync
- [x] AC-02: `/compliance` — default `clauses` omits `?section=` from URL
- [x] AC-03: `/compliance` — `?standard=` / `?clause=` deep links still work
- [x] AC-04: `/ims` — five sections with pill + filter-bar + `?section=` sync
- [x] AC-05: `/ims` — compliance hub chips + external destinations preserved
- [x] AC-06: Honest empty states unchanged (gaps, imported, mapping, ISMS)
- [x] AC-07: Vitest covers helpers + shell routing for both pages
- [ ] CI green — parent opens PR

## 6) Testing Evidence

- [x] Vitest — `complianceEvidenceHelpers.test.ts`, `imsDashboardHelpers.test.ts`
- [x] Vitest — `ComplianceEvidence.test.tsx`, `IMSDashboard.test.tsx` (section routing)
- [ ] CI green — pending PR

## 7) Critical Journeys Verified (CUJ)

- [x] CUJ-01: `/compliance` default — clause tree visible
- [x] CUJ-02: `/compliance?section=gaps` — gap analysis panel
- [x] CUJ-03: `/ims?section=mapping` — MAP-W1 honesty panel
- [x] CUJ-04: IMS hub ISMS chip → `?section=isms`

## 8) Observability & Ops

- **Playwright hooks:** `compliance-evidence-section-{clauses|evidence|gaps|imported}`, `ims-section-{overview|mapping|audit|review|isms}`

## 9) Verify steps (local)

```bash
cd /tmp/qgp-campaign-waves/assurance-ia-iso/frontend
npm run test -- src/pages/__tests__/complianceEvidenceHelpers.test.ts \
  src/pages/__tests__/imsDashboardHelpers.test.ts \
  src/pages/__tests__/ComplianceEvidence.test.tsx \
  src/pages/__tests__/IMSDashboard.test.tsx
```

Manual smoke:

1. `/compliance` — pills default to Clause View; click Gap Analysis → URL `?section=gaps`
2. `/compliance?standard=iso9001&clause=7.5` — lands on clauses with clause selected
3. `/ims` — hub cards + overview KPIs; `/ims?section=mapping` — scheme chips panel
4. Click ISMS hub card — URL `?section=isms`, ISMS tab active

## 10) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA
