# Permission Matrix

This document describes the permission model for the Quality Governance Platform API.

## Overview

All mutating endpoints (POST, PUT, PATCH, DELETE) must enforce authorization through permission checks. This ensures that only authorized users can perform actions that modify data or system state.

## Authorization Models

### 1. Permission-Based Authorization

Use `require_permission()` for fine-grained access control based on specific permissions.

**Pattern:**
```python
from typing import Annotated
from fastapi import Depends
from src.api.dependencies import require_permission
from src.domain.models.user import User

@router.post("/resources")
async def create_resource(
    data: ResourceCreate,
    current_user: Annotated[User, Depends(require_permission("resource:create"))],
) -> ResourceResponse:
    # Endpoint implementation
    pass
```

**Permission Format:**
- Format: `{resource}:{action}`
- Examples:
  - `audit:create` - Create audit templates
  - `audit:update` - Update audit templates
  - `risk:create` - Create risk entries
  - `investigation:update` - Update investigations
  - `workflow:execute` - Execute workflow steps

### 2. Role-Based Authorization

Use `require_role()` for role-based access control (when implemented).

**Pattern:**
```python
from typing import Annotated
from fastapi import Depends
from src.api.dependencies import require_role
from src.domain.models.user import User

@router.delete("/admin/resources/{id}")
async def delete_resource(
    resource_id: int,
    current_user: Annotated[User, Depends(require_role("admin"))],
) -> None:
    # Endpoint implementation
    pass
```

### 3. Superuser Authorization

Use `CurrentSuperuser` for endpoints that should only be accessible to superusers.

**Pattern:**
```python
from src.api.dependencies import CurrentSuperuser

@router.delete("/templates/{id}/permanent")
async def permanently_delete_template(
    template_id: int,
    current_user: CurrentSuperuser,
) -> None:
    # Superuser-only operation
    pass
```

## Rules

### Required Checks

1. **All mutating endpoints** (POST, PUT, PATCH, DELETE) MUST use one of:
   - `require_permission()`
   - `require_role()`
   - `CurrentSuperuser`

2. **Read-only endpoints** (GET) MAY use `CurrentUser` without additional permission checks, as they don't modify state.

### Prohibited Patterns

❌ **DO NOT** use `CurrentUser` alone on mutating endpoints:
```python
# ❌ VIOLATION
@router.post("/resources")
async def create_resource(
    data: ResourceCreate,
    current_user: CurrentUser,  # Missing permission check!
) -> ResourceResponse:
    pass
```

✅ **DO** use permission checks:
```python
# ✅ CORRECT
@router.post("/resources")
async def create_resource(
    data: ResourceCreate,
    current_user: Annotated[User, Depends(require_permission("resource:create"))],
) -> ResourceResponse:
    pass
```

## Permission Naming Convention

Follow the pattern: `{resource}:{action}`

### Common Resources
- `audit` - Audit templates and runs
- `risk` - Risk register entries
- `investigation` - Investigation records
- `workflow` - Workflow templates and instances
- `signature` - Digital signatures
- `rta` - Risk Treatment Actions
- `iso27001` - ISO 27001 controls
- `telemetry` - Telemetry data
- `planetmark` - Planet Mark data

### Common Actions
- `create` - Create new resources
- `update` - Modify existing resources
- `delete` - Remove resources (if soft-delete)
- `execute` - Execute workflows or processes
- `read` - Read access (typically not required for GET endpoints)

## Validation

The CI pipeline includes `scripts/validate_permissions.py` which automatically checks that all mutating endpoints have proper permission checks.

**Run manually:**
```bash
python scripts/validate_permissions.py
```

**Warn-only mode (for gradual migration):**
```bash
python scripts/validate_permissions.py --warn-only
```

## Migration Guide

When migrating existing endpoints:

1. Identify the appropriate permission for the operation
2. Replace `CurrentUser` with `Annotated[User, Depends(require_permission("resource:action"))]`
3. Ensure the permission exists in the permission system
4. Test the endpoint with users who have/don't have the permission
5. Update this document if adding new permission patterns

## Examples

### Creating a Resource
```python
@router.post("/audits", response_model=AuditResponse, status_code=status.HTTP_201_CREATED)
async def create_audit(
    audit_data: AuditCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> AuditResponse:
    service = AuditService(db)
    audit = await service.create_audit(
        audit_data.model_dump(),
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
    )
    return AuditResponse.model_validate(audit)
```

### Updating a Resource
```python
@router.patch("/audits/{audit_id}", response_model=AuditResponse)
async def update_audit(
    audit_id: int,
    audit_data: AuditUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> AuditResponse:
    service = AuditService(db)
    audit = await service.update_audit(
        audit_id,
        audit_data.model_dump(exclude_unset=True),
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
    )
    return AuditResponse.model_validate(audit)
```

### Superuser-Only Operation
```python
@router.delete("/templates/{template_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
async def permanently_delete_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Permanently delete an archived template (superuser only)."""
    service = AuditService(db)
    await service.permanently_delete_template(
        template_id,
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
    )
```

## See Also

- `src/api/dependencies.py` - Implementation of permission checking
- `scripts/validate_permissions.py` - CI validation script
- `docs/ARCHITECTURE.md` - Overall system architecture
