# Stage 4.0: Data Impact Statement

**Date**: 2026-01-05  
**PR**: #24  
**Stage**: 4.0 - Investigation + RCA-in-Template (Breaking Change)

---

## Executive Summary

**Pre-production greenfield project: No production data existed at the time of this change.**

The removal of the `root_cause_analyses` table and `/api/v1/rtas` endpoints has **zero data loss impact** because:
1. The project is in pre-production development phase
2. No persistent staging or production environments exist
3. All data is ephemeral (local development and CI test databases only)

---

## Environment Status

### Production Environment
**Status**: Does not exist  
**Impact**: None

### Staging Environment
**Status**: Does not exist (no persistent environment deployed)  
**Impact**: None

### Development Environment
**Status**: Local development databases only (ephemeral)  
**Impact**: Developers will need to run migrations to drop `root_cause_analyses` table

### CI/Test Environment
**Status**: Ephemeral PostgreSQL containers (created and destroyed per test run)  
**Impact**: None (migrations run automatically in CI)

---

## Breaking Changes

### Removed Endpoints
- `POST /api/v1/rtas` - Create RTA
- `GET /api/v1/rtas` - List RTAs
- `GET /api/v1/rtas/{id}` - Get RTA
- `PATCH /api/v1/rtas/{id}` - Update RTA
- `GET /api/v1/incidents/{id}/rtas` - List RTAs for incident

### Removed Database Table
- `root_cause_analyses` - Dropped via migration `02064fd78d6c`

### Replacement
- Investigation system with templates and runs
- RCA functionality now embedded within Investigation templates
- New endpoint: `GET /api/v1/incidents/{id}/investigations`

---

## Migration Strategy

### For Greenfield Deployment (Current State)
1. Run migrations in order:
   - `ee405ad5e788` - Add investigation_templates and investigation_runs tables
   - `02064fd78d6c` - Drop root_cause_analyses table
2. No data migration required (no existing data)

### For Hypothetical Production Deployment (Future Reference)
If this were deployed to a system with existing RCA data, the migration strategy would require:
1. Data export from `root_cause_analyses` table
2. Transformation script to convert RCA records to Investigation templates/runs
3. Import into new Investigation system
4. Validation of data integrity
5. Drop old table

**Note**: This is not applicable to the current deployment as no production data exists.

---

## Rollback Plan

### If Rollback Required
1. Revert PR #24 merge
2. Run migration downgrade: `alembic downgrade -1` (twice)
3. Restore `/api/v1/rtas` endpoints
4. Recreate `root_cause_analyses` table structure (empty)

**Data Recovery**: Not applicable (no data to recover in greenfield state)

---

## Risk Assessment

**Risk Level**: **LOW**

**Justification**:
- No production environment exists
- No persistent staging environment exists
- All data is ephemeral (local dev + CI)
- Breaking change is intentional and documented
- Full test coverage (169 tests passing)

---

## Approval

**Data Impact Reviewed By**: System Architect  
**Date**: 2026-01-05  
**Conclusion**: Zero data loss risk - greenfield deployment

---

## References

- PR #24: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/24
- Migration `ee405ad5e788`: Add investigation templates and runs
- Migration `02064fd78d6c`: Drop root_cause_analyses table
- ADR-0003: Readiness Probe Database Check
