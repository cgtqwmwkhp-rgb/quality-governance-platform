# Workforce engineer RBAC — dual gate (ACT-053)

## Summary

Engineer roster **writes** (`POST /api/v1/engineers/`, `POST /api/v1/engineers/sync-from-pams`) use a **dual gate**:

| Gate | Check | Purpose |
|------|--------|---------|
| RBAC permission | `engineer:create` on role facet | Fine-grained role catalog |
| Workforce manager | `admin` or `supervisor` role name, or `is_superuser` | Limits roster mutations to HSEQ/supervisor operators |

Granting `engineer:create` to a staff persona **without** admin/supervisor still returns **403** — this is intentional, not a defect.

## Operator guidance

- **Supervisor / HSEQ admin:** assign admin or supervisor role **and** ensure `engineer:create` is on the role facet (default manager roles include it).
- **Staff with engineer:create only:** can read own linked profile via `GET /engineers/by-user/me`; cannot create roster rows or run PAMS sync.
- **Frontend:** Employees page hides Add / Sync CTAs unless JWT roles include admin or supervisor (or superuser).

## Related

- Route implementation: `src/api/routes/engineers.py`
- Permission catalog tests: `tests/unit/test_require_permission_modules.py`
