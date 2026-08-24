# Master Defect Register — status sync (PX-332 re-issue)

**Issued:** 2026-08-02  
**Programme:** Run021 walk-away Phase 4 (`w6-register` / PX-332)  
**Authoritative CSV:** [`QGP-Run021-Defect-Log.csv`](./QGP-Run021-Defect-Log.csv)  
**Prior artefact:** `QGP-Run021-Cursor-Pack/02-defects/QGP-Run021-Defect-Log.csv` (208 rows, next free **PX-332**, almost all `Status=New`)  
**Measured tip:** `49235c25680858cd352e3283753c72b4a1dfc690`  
**Staging at w6-retest:** `20b85514333eea4867eb031402936fe193962e69` (one PR behind tip)

## What this re-issue does

1. **Checks the 208-row Run 021 CSV into the repo** under `docs/uat/` so the register is no longer only on a laptop pack.
2. **Status-syncs** walk-away closures that have measured PR / issue evidence (does **not** mass-mark the remaining ~200 UAT defects Fixed without retest).
3. **Consumes PX-332…PX-341** for the register meta-item, N-1…N-5, and programme items (B-13, C-24, C-33, C-34 / N-3 handoffs).
4. Sets **next free ID: PX-342**.

## Status updates on existing rows

| ID | Prior | New status | Evidence |
|---|---|---|---|
| **PX-312** | New | Partially closed — honesty | #1294 / #1352 removed false anonymity promise; walk-away keeps anonymous reporting **off**; UI hard-off **#1523 OPEN** |
| **PX-177** | New | Code closed / residue ops open | Soft-delete/archive **#1472 MERGED**; residue ops **#1524 OPEN** |
| **PX-125** | New | Ops in progress | Debris / purge markers addressed via walk-away residue track **#1524 OPEN** (primitive #1472) |

All other Run 021 rows remain at their prior Status (`New` / `Corrected` / …) until a measured retest says otherwise.

## New rows (PX-332 onward)

| ID | Title (short) | Status |
|---|---|---|
| **PX-332** | Register re-issue / status-sync required | Closed — register re-issued |
| **PX-333** | N-1 historic closure estate vs gate | Handed off — business (#1522) |
| **PX-334** | N-2 near-miss two-state lifecycle | Handed off — business (#1522) |
| **PX-335** | N-3 prod apps in `rg-qgp-staging` | Handed off — IT (#1520) |
| **PX-336** | N-4 taxonomy stubs | Open (linked PX-119/120) |
| **PX-337** | N-5 duplicate lookup categories | Open |
| **PX-338** | C-34 region split | Handed off — IT (#1519) |
| **PX-339** | C-33 App Insights empty / no traces | In progress — #1528 OPEN |
| **PX-340** | C-24 absent document-control / IMS tables | Code closed on tip (#1525/#1527); staging lag |
| **PX-341** | B-13 superuser tenant scope | Closed — code (#1510–#1518) |

## Walk-away board mapping (non-exhaustive)

| Board / plan item | Register impact |
|---|---|
| B-13 tenancy/authz PRs | **PX-341** Closed — code |
| C-24 Documents + IMS creates | **PX-340** Code closed on tip |
| Residue purge (prod/stg) | **PX-125** / **PX-177** ops open via #1524 |
| PX-312 keep-off + UI remove | **PX-312** partial; #1523 open |
| C-33 App Insights | **PX-339** in progress #1528 |
| IT handoffs C-34 / N-3 | **PX-338** / **PX-335** handed off |
| Business handoff pack | **PX-333** / **PX-334** (+ pack issue #1522) |
| w6-retest | Evidence: `docs/evidence/w6-retest-staging-p0-smoke-2026-08-02.md` |

## Honesty constraints

- **Handed off ≠ fixed.** IT/business tickets close the *programme* item under walk-away definition B; the underlying condition may still be true in Azure / data.
- **Code closed on tip ≠ live on staging/prod** until promote. Staging at retest lagged tip by #1527.
- **Do not treat Status=`New` as “never worked on”.** Many Run 021 defects have merged PRs; they stay `New` here until a UAT retest re-verifies the *observed* defect.

## Counts after sync

- Rows: **218** (208 prior + 10 new)
- Next free ID: **PX-342**
- P0 still largely open pending dedicated UAT retest of portal journeys (PX-119, PX-120, PX-155, PX-168, PX-178, PX-248, PX-255, PX-281, PX-315, PX-327, plus partial PX-312)
