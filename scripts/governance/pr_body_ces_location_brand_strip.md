# Change Ledger — CES location brand strip (PR-A)

## 1) Summary
- **Feature / Change name:** CES location normalisation — strip Plantexpand brand
- **User goal:** Pending Safety locations and Asset Register Site labels must not store “Plantexpand …” prefixes from CES Location cells.
- **In scope:** AC-01..AC-05
- **Out of scope:** Hide-removed toggle, evidence gallery, full CES re-import
- **Feature flag / kill switch:** N/A — additive parser + data cleanup

## 2) Impact Map
| File | Change |
|------|--------|
| `src/domain/services/ces_asset_import_parser.py` | `strip_company_brand_prefix` + apply in `split_location` |
| `alembic/versions/20260807_ces_strip_location_brand.py` | Rename/merge existing brand-prefixed locations; refresh `assets.site` |
| `tests/unit/test_ces_asset_import_service.py` | Real CES shape coverage |
| `scripts/governance/pr_body_ces_location_brand_strip.md` | This ledger |

## 3) Compatibility & Data Safety
- Parser still splits on `;` (company vs assignment)
- Brand-only assignment becomes `null` (no empty/junk location proposal)
- Migration merges into existing same-name location when present; otherwise renames in place
- Downgrade is no-op (labels kept)

## 4) Acceptance Criteria (AC)
- [x] AC-01: `Plantexpand Ltd ; Plantexpand Ltd Wickford` → assignment `Wickford`
- [x] AC-02: `… Workshop Hampton` → `Workshop Hampton`
- [x] AC-03: Vehicle+engineer rows do not create brand-only location names
- [x] AC-04: Existing `locations.name` starting with Plantexpand are renamed/merged
- [x] AC-05: Linked `assets.site` brand prefixes refreshed

## 5) Testing Evidence
- [x] `pytest tests/unit/test_ces_asset_import_service.py` (25 passed)

## 6) Critical Journeys (CUJ)
- [x] CUJ-01: CES dry-run/commit proposes site “Wickford” not “Plantexpand Ltd Wickford”
- [x] CUJ-02: Admin pending Safety locations no longer show brand-prefixed names after migrate

## 7) Observability & Ops
- No new metrics

## 8) Release Plan
1. Merge after CI green
2. Staging migrate → confirm pending location names
3. Prod tip==LIVE

## 9) Rollback Plan
- **Trigger:** Import creates wrong/empty sites for valid CES locations
- **Steps:** Revert deploy; migration leaves renamed rows (safe); parser revert restores prior behaviour for new imports
- **Owner:** Platform team

## 10) Evidence Pack
- CI linked on PR

## CES ↔ Asset Register column mapping
| CES spreadsheet | QGP |
|---|---|
| Location | Site (`location_id` / `site`) + Vehicle / Owner (parsed) |
| Equipment Type | Type (`asset_type`) |
| Make / Model / Capacity / Description | Name / metadata |
| Serial Number | Serial |
| Asset ID | Weak / often empty |
| QR Code | QR fields |
| Last / Next Inspection | Last inspection / Next ↑ (`expiry_date`) |
| Status | Status + Band (Fail→quarantined, Removed→decommissioned) |

## Vehicle count challenge (GY71SXM sample)
CES file: 65 rows = 32 Removed + 29 Pass + 2 Advisory + 2 NMA. By-vehicle board previously counted Removed kit — addressed in PR-B hide-removed.

---

# Gate Checklist
- [x] Gate 0: Scope lock + AC + Change Ledger complete
- [x] Gate 1: API/Data/UX contracts approved
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification
- [ ] Gate 4: Canary (N/A)
- [x] Gate 5: Production verification plan ready
