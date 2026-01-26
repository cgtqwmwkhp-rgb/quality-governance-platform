# EXP-001: Autosave + Draft Recovery for Portal Forms

**Status**: ACTIVE  
**Created**: 2026-01-26  
**Feature Flag**: `portal_form_autosave`

---

## 1. Hypothesis

**If** we implement automatic form saving to localStorage with draft recovery prompts,  
**Then** the portal incident report form abandonment rate will decrease by ≥15%,  
**Because** field workers frequently lose form data due to accidental navigation, network issues, or browser crashes.

---

## 2. Target Workflow

| Field | Value |
|-------|-------|
| Workflow ID | `portal-incident-report` |
| Workflow Name | Employee Incident Report Submission |
| Criticality | P0 |
| Steps | 5 |
| Max Duration | 30 seconds |

---

## 3. KPI Targets

| Metric | Baseline | Target | Guardrail |
|--------|----------|--------|-----------|
| Form abandonment rate | TBD (establish baseline) | -15% | +5% max |
| Form completion time | TBD | No change (+/-10%) | +20% max |
| Error rate | TBD | No change | +2% max |
| Draft recovery usage | N/A | ≥5% of sessions | - |

---

## 4. Implementation Details

### Feature Flag

```json
{
  "feature": "portal_form_autosave",
  "default": false,
  "rollout": {
    "staging": true,
    "canary": true,
    "production": false
  }
}
```

### Technical Design

1. **useFormAutosave Hook**
   - Debounced save to localStorage (500ms)
   - Storage key: `portal_form_draft_{formType}`
   - Draft expiry: 24 hours
   - PII-safe: No raw PII stored (use session tokens only)

2. **Draft Recovery UI**
   - Show recovery prompt on form mount if draft exists
   - Options: "Resume Draft" or "Start Fresh"
   - Clear draft on successful submission

3. **Storage Schema**
   ```typescript
   interface FormDraft {
     formType: string;
     data: Record<string, unknown>;
     step: number;
     savedAt: string; // ISO timestamp
     expiresAt: string; // ISO timestamp (24h from savedAt)
     version: string; // Schema version for migrations
   }
   ```

---

## 5. Guardrails

- [ ] No PII stored in localStorage (validated by security scan)
- [ ] Existing E2E tests pass
- [ ] UX Coverage gate remains GO
- [ ] No regressions in form submission success rate
- [ ] Storage quota handled gracefully (try/catch)

---

## 6. Rollout Plan

1. **Staging**: 100% (for testing)
2. **Canary**: 100% (for metrics collection)
3. **Production**: 0% initially, then gradual rollout based on metrics

---

## 7. Success Criteria

- Form abandonment rate decreases by ≥15%
- Draft recovery used in ≥5% of form sessions
- No increase in error rate
- Positive user feedback (if survey available)

---

## 8. Rollback Criteria

- Error rate increases by >2%
- Form completion time increases by >20%
- Security vulnerability discovered
- User complaints about draft recovery UX

---

## 9. Measurement Plan

### 9.1 Sample Definition (EXPLICIT)

**Primary Sample Event**: `exp001_form_submitted`
- This event is the **denominator** for all KPI calculations
- Evaluator uses `exp001_form_submitted` count as "samples"
- Minimum samples required: **100 per cohort**

### 9.2 Event Schema (Bounded Dimensions, No PII)

| Event Name | When Emitted | Dimensions |
|------------|--------------|------------|
| `exp001_form_opened` | Form component mounts | `formType`, `flagEnabled`, `hasDraft` |
| `exp001_draft_saved` | Draft written to localStorage | `formType`, `step` |
| `exp001_draft_recovered` | User clicks "Resume Draft" | `formType`, `draftAgeSeconds` |
| `exp001_draft_discarded` | User clicks "Start Fresh" | `formType`, `draftAgeSeconds` |
| `exp001_form_submitted` | Form submitted successfully | `formType`, `flagEnabled`, `hadDraft`, `stepCount` |
| `exp001_form_abandoned` | Session ends without submit | `formType`, `flagEnabled`, `lastStep`, `hadDraft` |

### 9.3 KPI Calculations

```
abandonment_rate = exp001_form_abandoned / (exp001_form_opened)
draft_recovery_usage = exp001_draft_recovered / (exp001_form_opened WHERE hasDraft=true)
completion_time = avg(submit_timestamp - open_timestamp) WHERE flagEnabled=true
error_rate = (exp001_form_submitted WHERE error=true) / exp001_form_submitted
```

### 9.4 Cohort Split

- **Treatment** (flagEnabled=true): Users with autosave enabled
- **Control** (flagEnabled=false): Users without autosave (if A/B testing)
- **Note**: For initial rollout, treatment-only measurement with historical baseline

---

## 10. No-PII Statement

This experiment collects:
- Form field values (non-PII only: contract, location type, timestamps)
- Form step progress
- Draft usage metrics

This experiment does NOT collect or store:
- Names or personal identifiers
- Email addresses or phone numbers
- Any data that could identify individuals

All form data in localStorage is keyed by session token, not user ID.

---

**Experiment Owner**: Principal Engineer  
**Review Date**: 2026-02-02
