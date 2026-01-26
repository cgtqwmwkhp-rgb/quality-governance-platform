# EXP-001 Rollout Plan: Autosave + Draft Recovery

**Date**: 2026-01-26  
**Decision**: ✅ **KEEP**  
**Evaluator Run**: [experiment_evaluation_EXP_001.json](../../artifacts/experiment_evaluation_EXP_001.json)

---

## 1. Decision Summary

| Criteria | Result |
|----------|--------|
| Minimum Samples | 112/100 ✅ |
| KPI Targets Met | 2/4 (50%) ✅ |
| Guardrails Breached | 0 ✅ |
| **Decision** | **KEEP** |

---

## 2. KPI Evidence

| KPI | Baseline | Target | Actual | Status |
|-----|----------|--------|--------|--------|
| Abandonment Rate | (historical) | -15% | **-18%** | ✅ EXCEEDED |
| Completion Time | baseline | ±0% | +2% | ➖ Within guardrail |
| Error Rate | 0% | 0% | 0.5% | ➖ Within guardrail |
| Draft Recovery Usage | N/A | ≥5% | **70%** | ✅ EXCEEDED |

**Key Findings**:
1. Abandonment rate reduced by 18% (exceeded -15% target)
2. Draft recovery feature highly adopted (70% of users with drafts recovered them)
3. Minor increase in completion time (+2%) but well within 20% guardrail
4. Negligible error rate (0.5%)

---

## 3. Rollout Schedule (Human Approval Required)

| Phase | Coverage | Start | Duration | Gate |
|-------|----------|-------|----------|------|
| **Staging** | 100% | 2026-01-26 | Complete | ✅ PASSED |
| **Canary** | 10% | Pending approval | 24h | Error rate < 2%, latency p95 < +20% |
| **Canary** | 50% | After 24h bake | 24h | Same gates |
| **Production** | 100% | After 48h bake | - | Final human approval |

---

## 4. Canary Orchestrator Policy

```yaml
feature_flag: portal_form_autosave
rollout:
  staging: 100
  canary: 10  # Start at 10%
  production: 0  # Disabled until approved

canary_policy:
  expansion_schedule:
    - { after_hours: 24, if_healthy: true, expand_to: 50 }
    - { after_hours: 48, if_healthy: true, expand_to: 100 }
  
  health_checks:
    - metric: error_rate
      threshold: 0.02
      action_if_breached: rollback
    - metric: latency_p95_delta
      threshold: 0.20
      action_if_breached: hold
    - metric: form_submission_success_rate
      threshold: 0.95
      action_if_breached: rollback

  rollback_policy:
    automatic: true
    notification: ["platform-team@example.com"]
```

---

## 5. Monitoring During Rollout

### Telemetry Events to Watch

| Event | Expected Trend | Alert If |
|-------|----------------|----------|
| `exp001_form_submitted` | Stable/increasing | Count drops >20% |
| `exp001_form_abandoned` | Decreasing | Increases >10% |
| `exp001_draft_recovered` | Stable | N/A |
| Error rate | <2% | Exceeds 2% |

### Control Tower Dashboard

Add these panels:
1. EXP-001 Event Counts (time series)
2. Abandonment Rate (treatment vs historical)
3. Draft Recovery Usage Rate
4. Error Rate by Flag Status

---

## 6. Rollback Procedure (If Needed)

```bash
# Immediate rollback (disable feature flag)
curl -X PATCH https://$API_HOST/api/v1/feature-flags/portal_form_autosave \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"enabled": false}'

# Clear any corrupted drafts (if needed)
curl -X DELETE https://$API_HOST/api/v1/admin/clear-portal-drafts \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## 7. Approval Checklist

- [ ] **Engineering Lead**: Approve canary expansion to 10%
- [ ] **QA Lead**: Confirm no regressions in E2E tests
- [ ] **Product Owner**: Approve production rollout after canary bake
- [ ] **SRE**: Confirm monitoring and alerting in place

---

## 8. No-PII Statement

This rollout:
- Does not change any PII handling
- Telemetry contains only bounded dimensions (no free text)
- LocalStorage drafts contain form metadata only (no PII fields)
- All session IDs are anonymous and not linked to users

---

**Prepared by**: Principal Engineer (Experimentation + SRE + QA)  
**Awaiting Approval**: Human-in-loop required for canary expansion
