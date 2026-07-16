# Change Ledger

## Summary
- Fix `/risk-register/trends` 500 caused by binding timezone-aware cutoffs against naive `assessment_date` columns.
- Harden monthly average calculation when score lists are empty; keep `include_movers` contract.

## Acceptance Criteria
- [x] AC-01: `GET /api/v1/risk-register/trends` returns 200 (empty list or series) on prod tip
- [x] AC-02: `include_movers=true` returns `{series, top_movers}` without 500
- [x] AC-03: Heat map page loads trends honestly (empty-state when no history)

## CUJ
- [x] CUJ-01: Risk Register heatmap loads; sparkline/top movers section does not error the workspace

## Gates
- [x] Unit: naive cutoff + include_movers
- [x] No schema/migration change
- [x] OpenAPI additive only (no break)

## Tip LIVE
- Merge squash; wait staging→prod; verify `/api/v1/meta/version` and `/trends` 200.
