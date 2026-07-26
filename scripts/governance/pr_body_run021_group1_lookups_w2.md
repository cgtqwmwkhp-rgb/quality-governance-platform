# Change Ledger (CL-RUN021-GROUP1-LOOKUPS-W2)

## 1) Summary
- **Feature / Change name:** Run021 Wave 2 — GROUP 1 residual code (lookup seed + publish guard)
- **User goal:** Unconfigured environments never dead-end portal intake; admins cannot publish forms whose required fields map to empty lookup catalogs; portal warnings only mention lookups the form actually uses (PX-284).
- **In scope:** Idempotent UK lookup defaults seed (migration + startup); form publish validation (POST publish + PATCH is_published); contextual portal catalog warnings; unit tests; Change Ledger
- **Out of scope:** Production data writes; customers seed; search/Layout/Documents; audits UI; workforce skills matrix; investigation closure i18n; `.size-limit.json`
- **Defects addressed:** PX-119/PX-120 residual code path; PX-121 publish guard; PX-284 banner honesty

## 2) Impact Map
- **Backend:** `lookup_defaults_seed_data.py`, `lookup_defaults_seed.py`, `form_publish_validation.py`; `form_config_service.publish_template`; `form_config` publish route; Alembic `20260828_seed_lookup_defaults`; startup hook in `main.py`
- **Frontend:** `formLookupFields.ts`; `PortalDynamicForm.tsx` contextual warnings
- **APIs:** No new endpoints — publish returns 422 when lookup catalogs empty
- **Database:** Migration inserts defaults only when tenant category is empty

## 3) Compatibility & Data Safety
- **Strategy:** Additive, idempotent — never overwrites existing lookup rows
- **Breaking changes:** None — publish may now 422 where it previously silently published broken forms
- **Rollback:** Revert PR; seeded rows remain (non-destructive downgrade)

## 4) Acceptance Criteria
- [x] AC-01: Empty tenant gets UK defaults for six lookup categories on migrate/startup
- [x] AC-02: Existing configured categories are never duplicated or replaced
- [x] AC-03: Publish blocked when required `person_role`/`contract`/lookup select has zero active options
- [x] AC-04: Complaint form no longer shows workforce-roles banner when form has no role lookup (PX-284)
- [x] AC-05: Unit tests cover seed idempotency, publish guard, and banner logic

## 5) Testing Evidence
- [x] `tests/unit/test_lookup_defaults_seed.py`
- [x] `tests/unit/test_form_publish_validation.py`
- [x] `tests/unit/test_form_config_service.py` (publish guard)
- [x] `frontend/src/helpers/__tests__/formLookupFields.test.ts`

## 6) Residual ops steps (production)
1. **Deploy migration** — seeds defaults only for categories still empty per tenant; does not replace admin values.
2. **If prod still has orphaned `tenant_id IS NULL` lookup rows** — run/re-run migration `20260827_lookup_tenant_fix` (merged #1303) to adopt into tenant scope; this PR does not write prod data directly.
3. **Customers** — still require contract-specific configuration; not auto-seeded.
4. **Verify** `/portal/report/incident` Role dropdown populated after deploy + any tenant adoption migration.

## 7) Gate 0
- [x] Scope lock + AC defined + Change Ledger complete
