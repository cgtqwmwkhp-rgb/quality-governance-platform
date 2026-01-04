# MyPy Error Triage

## Category 1: Missing Type Annotations / Any Returns (8 errors)
**Files**: `src/core/security.py`, `src/api/dependencies/__init__.py`

1. `src/core/security.py:17` - Returning Any from `verify_password()` → **Fix**: Add explicit `bool` cast
2. `src/core/security.py:22` - Returning Any from `get_password_hash()` → **Fix**: Add explicit `str` cast
3. `src/core/security.py:51` - Returning Any from `create_access_token()` → **Fix**: Add explicit `str` cast
4. `src/core/security.py:70` - Returning Any from `create_refresh_token()` → **Fix**: Add explicit `str` cast
5. `src/core/security.py:81` - Returning Any from `decode_token()` → **Fix**: Add explicit cast
6. `src/api/dependencies/__init__.py:35` - `user_id` assignment from `Any | None` → **Fix**: Add explicit `str` cast

## Category 2: Type Mismatch in Dict Literals (2 errors)
**File**: `src/infrastructure/database.py`

7. `src/infrastructure/database.py:28` - Dict entry "pool_size": 10 (int) vs expected bool → **Fix**: Use `typing.Any` or proper dict type
8. `src/infrastructure/database.py:29` - Dict entry "max_overflow": 20 (int) vs expected bool → **Fix**: Use `typing.Any` or proper dict type

## Category 3: Attribute Access on Generic Type (1 error)
**File**: `src/services/reference_number.py`

9. `src/services/reference_number.py:54` - "type" has no attribute "reference_number" → **Fix**: Add proper type annotation or use `typing.cast`

## Category 4: Incorrect Type Usage (2 errors)
**Files**: `src/api/routes/users.py`

10. `src/api/routes/users.py:105` - Sequence[User] vs Iterable[Role] → **Fix**: Likely a copy-paste error, check logic
11. `src/api/routes/users.py:158` - Sequence[User] vs Iterable[Role] → **Fix**: Likely a copy-paste error, check logic

## Category 5: Assignment Type Mismatch (1 error)
**File**: `src/api/routes/standards.py`

12. `src/api/routes/standards.py:210` - Standard assigned to Clause variable → **Fix**: Check logic or fix variable name

## Category 6: None-Handling in Operations (2 errors)
**File**: `src/api/routes/audits.py`

13. `src/api/routes/audits.py:567` - Division by None → **Fix**: Add None check before operation
14. `src/api/routes/audits.py:567` - Comparison with None → **Fix**: Add None check before operation

## Fix Strategy
1. Start with Category 1 (security.py) - add explicit casts
2. Fix Category 2 (database.py) - use proper dict typing
3. Fix Category 3 (reference_number.py) - add type annotation
4. Fix Categories 4-6 (route files) - fix logic errors or add None checks
