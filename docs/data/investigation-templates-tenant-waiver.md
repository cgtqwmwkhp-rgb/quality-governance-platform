# Investigation templates tenant_id — waived NOT NULL (R77)

**Status:** WAIVED for DB `NOT NULL`  
**Wave:** GT schema wave 2 (`20260720_*`)  
**Catalog:** `docs/governance/tenant_id_catalog_exceptions.json` → `investigation_templates`

## Why NOT NULL is waived

- Investigation templates are a shared library; default template id=1 may be global.
- Child spine (`investigation_template_sections` / `fields`) already requires `tenant_id`.
- Runs already enforce `tenant_id` NOT NULL via fail-safe migrations.

## What landed instead

- App stamps `tenant_id` on auto-created default templates when known
  (`get_or_create_default_template(..., tenant_id=)`).
- API create paths already set `tenant_id=current_user.tenant_id`.

## Residual honesty

Shared/orphan template rows may remain nullable by design. Do not invent `tenant_id=1`.
