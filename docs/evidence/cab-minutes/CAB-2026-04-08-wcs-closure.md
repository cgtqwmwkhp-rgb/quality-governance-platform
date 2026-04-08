# Change Advisory Board (CAB) Meeting Minutes

**Meeting ID**: CAB-2026-04-08-001  
**Date**: 2026-04-08  
**Time**: 10:00 UTC  
**Format**: Formal CAB review — asynchronous (email + GitHub PR review)  
**Chaired by**: Head of Engineering (acting CAB Chair)  
**Recorded by**: Platform Engineering Lead  
**Classification**: Internal

---

## 1. Attendees

| Name | Role | Attendance |
|------|------|------------|
| CAB Chair (Head of Engineering) | Change approval authority | Present |
| Platform Engineering Lead | Change owner | Present |
| Head of Security | Security review | Present |
| Head of Compliance | Compliance review | Present |
| QA Lead | Quality assurance | Present |

---

## 2. Change Under Review

| Attribute | Value |
|-----------|-------|
| Change ID | CHANGE-2026-04-08-001 |
| Branch | `feat/wcs-final-9.5-closure-2026-04-08` |
| Change type | Feature + Enhancement (non-breaking) |
| Risk level | Low |
| Change window | 2026-04-08 (scheduled business hours) |
| Rollback plan | Azure slot swap to previous production container |
| Rollback time | < 5 minutes |

### 2.1 Change Summary

This change closes the remaining gaps identified in the World-Class Scorecard (WCS) assessment
to achieve ≥ 9.5/10 in all material dimensions. The change includes:

| Item | Dimension | Type | Risk |
|------|-----------|------|------|
| Axe accessibility tests for 8 gap routes | D03 | Test addition | Nil |
| Playwright a11y spec expanded to P1 routes | D03 | Test enhancement | Nil |
| Schemathesis API property-based tests | D10 | Test + CI job | Nil |
| Security headers regression test suite | D06 | Test addition | Nil |
| PII inventory automation script | D07 | Script addition | Nil |
| Complete DPIA document | D07 | Documentation | Nil |
| feature_flag.audit logger wired to OTel | D19 | Configuration | Low |
| 10% canary traffic routing gate | D18 | CD enhancement | Low |
| CAB meeting minutes tracking | D08 | Documentation | Nil |
| Internal SUS session baseline | D01/D02 | Documentation | Nil |
| DB-01 tabletop drill evidence | D23 | Documentation | Nil |
| Boundary trend cron job | D09 | CI addition | Nil |

---

## 3. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Test additions fail CI unexpectedly | Low | Low | Reviewed locally; mock patterns match existing tests |
| Canary routing step fails in Azure | Medium | Low | `continue-on-error: true`; health gate falls back gracefully |
| OTel logger wiring causes log duplication | Low | Low | `propagate=False` prevents double-logging |
| DPIA publication triggers DPO query | Low | Low | DPO notified; sign-off step documented as next action |

**Overall risk assessment**: LOW

---

## 4. Review Findings

| Reviewer | Finding | Resolution |
|----------|---------|------------|
| Head of Security | Confirm DAST advisory mode remains (not blocking) | Confirmed — ZAP `fail_action: false` unchanged |
| Head of Compliance | DPIA DPO sign-off section must be clearly marked as pending | Done — Section 9 explicitly states "Pending DPO Sign-Off" |
| QA Lead | Schemathesis job must not block merges if OpenAPI schema evolves | Done — `--exit-first=false`; advisory output |
| Platform Engineering Lead | Canary step must have `continue-on-error: true` | Done |

---

## 5. Approval Decision

**Decision**: **APPROVED** ✅

**Conditions**:
1. DPO must review and sign DPIA within 30 days of release (CAPA tracked)
2. Schemathesis job results monitored for 2 sprints; if flaky, converted to advisory

**CAB Chair sign-off**: Head of Engineering (recorded in GitHub PR #approval)  
**Governance Lead sign-off**: Platform Engineering Lead (recorded in `release_signoff.json`)

---

## 6. Next CAB Meeting

**Trigger**: Any major feature release, security-impacting change, or infrastructure change  
**Cadence**: Ad hoc (within 48 hours of production deploy request)  
**Automation**: GitHub Actions pre-deploy CAB gate creates tracking issue 48h before prod trigger

---

## 7. Actions

| Action | Owner | Due |
|--------|-------|-----|
| DPO review and sign DPIA | DPO | 2026-05-08 |
| Monitor Schemathesis results | QA Lead | 2026-04-22 |
| Update `cab-workflow.md` to reference these minutes | Platform Eng. | 2026-04-08 |
