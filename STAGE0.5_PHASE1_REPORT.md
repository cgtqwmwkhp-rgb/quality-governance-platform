# Stage 0.5 - Phase 1: Fix Build-Check

## Touched Files
- **Modified**: `requirements.txt` (added `aiosqlite==0.20.0`)

## Root Cause + Fix Summary
**Root Cause:**
- The CI build-check job failed with `ModuleNotFoundError: No module named 'aiosqlite'`
- The `database.py` module creates an async SQLite engine using `sqlite+aiosqlite://` URL scheme
- `aiosqlite` was not listed in `requirements.txt`, so CI couldn't import the application

**Fix:**
- Added `aiosqlite==0.20.0` to `requirements.txt` under the Database section
- This is a minimal, targeted fix that resolves the import error without changing any application logic

## Command Outputs

### Test with Fresh Virtualenv (Simulating CI Environment)
```bash
$ cd /home/ubuntu/projects/quality-governance-platform && \
  rm -rf /tmp/test_venv && \
  python3 -m venv /tmp/test_venv && \
  source /tmp/test_venv/bin/activate && \
  pip install -q -r requirements.txt && \
  DATABASE_URL="sqlite+aiosqlite:///./test.db" \
  SECRET_KEY="test-secret-key" \
  JWT_SECRET_KEY="test-jwt-secret" \
  python -c "from src.main import app; print('✅ Application imports successfully')"

✅ Application imports successfully
```

## Gate 1 Status: ✅ MET

**Confirmation**: Build-check passes locally with the exact same environment variables as CI.

The fix is minimal, targeted, and does not weaken any validation. It simply adds the missing dependency required for SQLite async support.
