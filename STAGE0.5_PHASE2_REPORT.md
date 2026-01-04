# Stage 0.5 - Phase 2: Fix MyPy Type Errors

## Touched Files
- **Modified**: `src/core/security.py` (added explicit type casts for bcrypt/JWT returns)
- **Modified**: `src/infrastructure/database.py` (added `dict[str, Any]` type annotation)
- **Modified**: `src/api/dependencies/__init__.py` (added explicit cast for user_id)
- **Modified**: `src/services/reference_number.py` (added `type[Any]` annotation + type ignore)
- **Modified**: `src/api/routes/users.py` (added type ignore comments for SQLAlchemy relationship assignment)
- **Modified**: `src/api/routes/standards.py` (added type ignore comment for scalar_one assignment)
- **Modified**: `src/api/routes/audits.py` (added None check before division)

## Root Cause + Fix Summary

### Category 1: Missing Type Annotations / Any Returns (6 errors)
**Root Cause**: Third-party libraries (passlib, python-jose) return `Any`, causing mypy to complain about untyped returns.

**Fix**: Added explicit type casts:
- `bool(pwd_context.verify(...))` for password verification
- `str(pwd_context.hash(...))` for password hashing
- `str(jwt.encode(...))` for JWT token encoding
- `dict(payload)` for JWT token decoding
- `str(user_id_raw)` for user ID extraction from JWT payload

### Category 2: Type Mismatch in Dict Literals (2 errors)
**Root Cause**: `engine_kwargs` dict was inferred as `dict[str, bool]` but contained `int` values for pool settings.

**Fix**: Added explicit type annotation: `engine_kwargs: dict[str, Any]`

### Category 3: Attribute Access on Generic Type (1 error)
**Root Cause**: Generic `type` parameter doesn't expose model-specific attributes like `reference_number`.

**Fix**: Changed parameter type to `type[Any]` with `# type: ignore[misc]` comment (tracked as acceptable for generic model handling)

### Category 4: SQLAlchemy Relationship Assignment (2 errors)
**Root Cause**: SQLAlchemy's `scalars().all()` returns `Sequence[T]` but mypy expects `Iterable[T]` for relationship assignment.

**Fix**: Added `# type: ignore[arg-type]` comments (SQLAlchemy-specific limitation, runtime-safe)

### Category 5: Assignment Type Mismatch (1 error)
**Root Cause**: `scalar_one()` return type inference issue when reassigning to the same variable.

**Fix**: Added `# type: ignore[assignment]` comment (mypy inference limitation, runtime-safe)

### Category 6: None-Handling in Operations (2 errors)
**Root Cause**: `total_questions` could be `None`, causing division and comparison errors.

**Fix**: Added explicit None check before division operation

## Command Outputs

```bash
$ cd /home/ubuntu/projects/quality-governance-platform && \
  source venv/bin/activate && \
  mypy src/ --ignore-missing-imports

Success: no issues found in 38 source files
```

## Type Ignore Usage Summary
- **Total type ignores**: 4
- **All are error-code-specific**: ✅ Yes
- **All have clear context**: ✅ Yes
- **Reasons**:
  - `[misc]`: Generic type handling in reference number service (1)
  - `[arg-type]`: SQLAlchemy relationship assignment (2)
  - `[assignment]`: SQLAlchemy scalar_one type inference (1)

## Gate 2 Status: ✅ MET

**Confirmation**: MyPy passes locally with 0 errors across all 38 source files.

All fixes are minimal and targeted. Type ignores are used only where necessary due to third-party library limitations (SQLAlchemy) and are properly scoped with error codes.
