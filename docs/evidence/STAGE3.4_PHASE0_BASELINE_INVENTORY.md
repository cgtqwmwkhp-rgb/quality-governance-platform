# Stage 3.4 Phase 0: Baseline Inventory

**Date**: 2026-01-05  
**Purpose**: Inventory reference_number usage and 409 behavior across modules before contract tightening.

---

## Modules with reference_number

All modules inherit from `ReferenceNumberMixin` (defined in `src/domain/models/base.py`):

```python
reference_number: Mapped[str] = mapped_column(
    String(20),
    unique=True,
)
```

### Module Inventory

| Module | Model | Reference Format | Unique Constraint |
|--------|-------|------------------|-------------------|
| Policies | Policy | POL-YYYY-NNNN | ✅ Yes (DB unique) |
| Incidents | Incident | INC-YYYY-NNNN | ✅ Yes (DB unique) |
| Complaints | Complaint | CMP-YYYY-NNNN | ✅ Yes (DB unique) |
| RTAs | RoadTrafficCollision | RTA-YYYY-NNNN | ✅ Yes (DB unique) |
| RTA Actions | RTAAction | RTAA-YYYY-NNNN | ✅ Yes (DB unique) |
| RTA Analysis | RootCauseAnalysis | RCA-YYYY-NNNN | ✅ Yes (DB unique) |
| Audits | AuditRun | AUD-YYYY-NNNN | ✅ Yes (DB unique) |
| Audit Findings | AuditFinding | AUDF-YYYY-NNNN | ✅ Yes (DB unique) |
| Complaint Actions | ComplaintAction | CMPA-YYYY-NNNN | ✅ Yes (DB unique) |
| Incident Actions | IncidentAction | INCA-YYYY-NNNN | ✅ Yes (DB unique) |
| Risks | Risk | RISK-YYYY-NNNN | ✅ Yes (DB unique) |

**Total**: 11 models with reference_number

---

## Current 409 Behavior Per Module

### Policies

**Status**: ✅ Deterministic duplicate detection implemented (Stage 3.3.1)

**Behavior**:
- Optional `reference_number` field in `PolicyCreate` schema
- Pre-insert duplicate check if `reference_number` is provided
- Returns 409 with canonical envelope if duplicate found
- Falls back to auto-generation if not provided

**Code Location**: `src/api/routes/policies.py` lines 36-46

```python
if policy_data.reference_number:
    reference_number = policy_data.reference_number
    # Check for duplicate reference number
    existing = await db.execute(
        select(Policy).where(Policy.reference_number == reference_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Policy with reference number {reference_number} already exists",
        )
```

**Test Coverage**: ✅ Yes - `test_409_conflict_canonical_envelope`

---

### Incidents

**Status**: ⚠️ No explicit 409 handling

**Behavior**:
- Auto-generated reference_number only
- No optional field in `IncidentCreate` schema
- IntegrityError would occur if duplicate somehow created
- No IntegrityError → 409 mapping

**Code Location**: `src/api/routes/incidents.py` lines 29-42

```python
# Generate reference number (format: INC-YYYY-NNNN)
year = datetime.now(timezone.utc).year
count_result = await db.execute(select(sa_func.count()).select_from(Incident))
count = count_result.scalar_one()
reference_number = f"INC-{year}-{count + 1:04d}"
```

**Test Coverage**: ❌ No 409 tests

---

### Complaints

**Status**: ⚠️ No explicit 409 handling

**Behavior**:
- Auto-generated reference_number only
- No optional field in `ComplaintCreate` schema
- IntegrityError would occur if duplicate somehow created
- No IntegrityError → 409 mapping

**Code Location**: `src/api/routes/complaints.py` lines 29-42

```python
# Generate reference number (format: CMP-YYYY-NNNN)
year = datetime.now(timezone.utc).year
count_result = await db.execute(select(sa_func.count()).select_from(Complaint))
count = count_result.scalar_one()
reference_number = f"CMP-{year}-{count + 1:04d}"
```

**Test Coverage**: ❌ No 409 tests

---

### RTAs

**Status**: ⚠️ No explicit 409 handling

**Behavior**:
- Auto-generated reference_number only
- No optional field in `RTACreate` schema
- IntegrityError would occur if duplicate somehow created
- No IntegrityError → 409 mapping

**Code Location**: `src/api/routes/rtas.py` lines 29-42

```python
# Generate reference number (format: RTA-YYYY-NNNN)
year = datetime.now(timezone.utc).year
count_result = await db.execute(select(sa_func.count()).select_from(RoadTrafficCollision))
count = count_result.scalar_one()
reference_number = f"RTA-{year}-{count + 1:04d}"
```

**Test Coverage**: ❌ No 409 tests

---

### Other Modules

**Status**: Not yet implemented (no API endpoints)

Modules with reference_number but no API endpoints:
- RTA Actions
- RTA Analysis
- Audits
- Audit Findings
- Complaint Actions
- Incident Actions
- Risks (has API but no create endpoint with reference_number)

---

## Canonical 409 Contract (Decided)

Based on Stage 3.3.1 implementation and error envelope standards:

### HTTP Status
- **Status Code**: 409 Conflict

### Response Body
```json
{
  "error_code": "409",
  "message": "<human-readable message>",
  "details": "<additional context>",
  "request_id": "<non-empty UUID>"
}
```

### Contract Requirements
1. `error_code` MUST be a string equal to "409"
2. `message` MUST be present and non-empty
3. `details` MUST be present (may be empty string)
4. `request_id` MUST be present and non-empty (UUID format)
5. All keys MUST be present in stable order

### Example
```json
{
  "error_code": "409",
  "message": "Conflict",
  "details": "Policy with reference number POL-2026-9999 already exists",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

## Phase 1-6 Scope (Preliminary)

### Phase 1: Guard PolicyCreate.reference_number
- **Risk**: Optional reference_number could be used to bypass auto-generation in production
- **Solution**: Require admin permission or restrict to non-production environments
- **Scope**: 1 module (Policies)

### Phase 2: Standardize 409 Handling
- **Target**: Incidents (as representative module)
- **Approach**: Add IntegrityError → 409 mapping in exception handler
- **Scope**: 1-2 modules (Incidents + optionally Complaints)

### Phase 3: Runtime Error Envelope Completeness
- **Target**: Policies, Incidents, Complaints
- **Verify**: 403/404/409 canonical envelopes with non-empty request_id
- **Scope**: Extend existing runtime contract tests

### Phase 4: OpenAPI Invariants Upgrade
- **Target**: `scripts/validate_openapi_contract.py`
- **Add**: Error envelope schema validation for 403/404/409
- **Scope**: 1 script + regenerate OpenAPI spec

### Phase 5: Acceptance Pack Enforcement
- **Target**: PR template + validator
- **Add**: Required fields validation (CI run URL, SHA, touched files, rollback)
- **Scope**: 2-3 files (template, validator, CI config)

### Phase 6: Evidence + Acceptance Pack
- **Target**: Create comprehensive acceptance pack
- **Scope**: Documentation + evidence collection

---

## Gate 0 Assessment

**Question**: Does this scope expand into new feature endpoints or schema expansion?

**Answer**: ❌ NO

**Justification**:
- No new endpoints being created
- No new modules being added
- Only hardening existing contracts and safety measures
- Schema changes are minimal (permission checks, not new fields)

**Gate 0**: ✅ PASS

---

**End of Phase 0 Inventory**
