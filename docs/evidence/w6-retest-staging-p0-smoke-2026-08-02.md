# w6-retest — Staging P0 API (+ light UI) smoke

**When:** 2026-08-02T21:09–21:14Z  
**Base API:** https://qgp-staging-plantexpand.azurewebsites.net  
**Frontend (SWA staging):** https://purple-water-03205fa03-staging.6.azurestaticapps.net  
**Accounts:** `~/Library/Application Support/qgp/staging-uat-accounts.txt` (`uat_employee`, `uat_manager`, `uat_viewer`)  
**Programme:** Run021 walk-away Phase 4 (`w6-retest`)

## SHAs

| Layer | SHA | Note |
|---|---|---|
| **Git tip (`origin/main`)** | `49235c25680858cd352e3283753c72b4a1dfc690` | Includes C-24 IMS (#1527) |
| **Staging `GET /api/v1/meta/version` `build_sha`** | `20b85514333eea4867eb031402936fe193962e69` | C-24 Documents cluster (#1525); **one PR behind tip** |
| Staging `build_time` | `2026-08-02T20:36:27Z` | |
| Staging `environment` | `staging` | |

## Results summary

| Check | Expected | Actual | Verdict |
|---|---|---|---|
| GET `/api/v1/meta/version` | 200 + `build_sha` | 200 → `20b85514…` | **PASS** (record lag vs tip) |
| Employee POST INC | 201 | 201 → `INC-2026-0056` | **PASS** |
| Employee POST RTA | 201 | 201 → `RTA-2026-0006` | **PASS** |
| Employee POST COMP | 201 | 201 → `COMP-2026-0021` | **PASS** |
| Employee POST NM | 201 | 201 → `NM-2026-0005` (requires `contract`/`contract_other` or `contract_id`) | **PASS** after valid payload |
| Viewer POST INC/RTA/COMP/NM | 403 | 403 all four | **PASS** |
| Document list with `document:read` | 200 for a principal holding `document:read` | UAT roles lack `document:read` → 403 `PERMISSION_DENIED` | **BLOCKED by harness** (not a product regression vs prior notes) |
| UI login (viewer) | Reach authenticated shell | Login → `/dashboard` | **PASS** (light) |

## Detail — creates

Tag prefix: `[WALKAWAY-W6-RETEST-…]` (safe soft-delete candidates).

### Employee (`uat_employee`, permissions include `*:create` + `*:read` for incident/rta/complaint/near_miss)

| Module | HTTP | Reference |
|---|---:|---|
| Incidents | 201 | `INC-2026-0056` |
| RTAs | 201 | `RTA-2026-0006` |
| Complaints | 201 | `COMP-2026-0021` |
| Near misses | 201 | `NM-2026-0005` |

Near-miss note: minimal OpenAPI-required fields alone return **422** (`Provide contract_id (preferred) or a legacy contract code`). Passing `contract=OTHER` + `contract_other=…` (same shape as prior CUJ residue `NM-2026-0003`) yields **201**. Description also requires `minLength: 10`.

### Viewer (`uat_viewer` — read-only case lists; deliberately no `rta:read`, no creates)

| Module | HTTP |
|---|---:|
| INC / RTA / COMP / NM create | **403** |

### Documents

All three UAT roles:

```text
GET /api/v1/documents/ → 403
Permission 'document:read' required
```

Role permission strings measured via `GET /api/v1/auth/me`:

- `uat_employee`: `complaint|incident|near_miss|rta` create+read only  
- `uat_manager`: same + updates + `action:*` — **no** `document:read`  
- `uat_viewer`: complaint/incident/near_miss read only  

Semantic search (`GET /api/v1/documents/search/semantic`) likewise 403 for these accounts (C-2 / #1518 gates on `document:read` — consistent).

**Harness gap:** no staging UAT principal currently carries `document:read`. Prior account notes already documented case-module authz only. To close this cell, grant `document:read` to a staging UAT role (or use a document-admin account) and re-run list.

## Light UI smoke

| Step | Result |
|---|---|
| Open SWA staging `/login` | 200 — login form renders |
| Sign in as `uat.viewer@example.com` | Navigates to `/dashboard` |

Full portal multi-step create CUJ was **not** re-run in the browser this pass (API creates cover P0 raise paths).

## Regressions vs prior retest notes

Prior measured proof (staging UAT accounts file, ~29 Jul 2026):

- viewer POST `/incidents/` → 403  
- employee POST `/incidents/` → 201 → `INC-2026-0050`  
- employee GET `/rtas/` → 200  

**This pass:**

| Prior | Now | Regression? |
|---|---|---|
| Viewer create 403 | Viewer create 403 (all four modules) | No |
| Employee INC 201 | Employee INC/RTA/COMP/NM 201 | No — expanded coverage still green |
| (documents not asserted on UAT roles) | documents 403 without `document:read` | No — harness limitation unchanged |
| Staging tip parity assumed | Staging `20b85514` vs tip `49235c25` | **Promote lag** — IMS C-24 (#1527) not yet on staging |

No P0 create/authz regression observed against the prior notes.

## Machine-readable companion

See `w6-retest-staging-p0-smoke-2026-08-02.json` in this directory for the structured API result dump (no passwords).
