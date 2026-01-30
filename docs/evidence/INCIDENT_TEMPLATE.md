# Incident Report: [INCIDENT_ID]

> **Template Version**: 1.0  
> **Last Updated**: 2026-01-30  
> **Status**: [OPEN | INVESTIGATING | MITIGATED | CLOSED]

---

## Quick Reference

| Field | Value |
|-------|-------|
| **Incident ID** | `INC-YYYY-MM-DD-SHORT_DESC` |
| **Severity** | SEV1 / SEV2 / SEV3 / SEV4 |
| **Status** | OPEN / INVESTIGATING / MITIGATED / CLOSED |
| **Opened** | YYYY-MM-DDTHH:MM:SSZ |
| **Closed** | YYYY-MM-DDTHH:MM:SSZ |
| **Duration** | X hours Y minutes |
| **Owner** | @github-username |
| **On-call** | @github-username |

---

## 1. Impact

### Customer Impact
<!-- Describe who was affected and how -->
- **Users Affected**: All / Subset (describe) / None
- **Features Impacted**: List affected features
- **Error Observed**: HTTP 5xx / Timeout / Data corruption / etc.

### Business Impact
<!-- Quantify if possible -->
- Requests failed: X
- Duration of impact: X minutes
- Revenue impact: N/A or estimate

---

## 2. Timeline

| Time (UTC) | Event |
|------------|-------|
| YYYY-MM-DDTHH:MM:SSZ | First customer report / alert triggered |
| YYYY-MM-DDTHH:MM:SSZ | Investigation started |
| YYYY-MM-DDTHH:MM:SSZ | Root cause identified |
| YYYY-MM-DDTHH:MM:SSZ | Fix deployed |
| YYYY-MM-DDTHH:MM:SSZ | Incident closed |

---

## 3. Root Cause

### Summary
<!-- One paragraph explaining what went wrong -->


### Technical Details
<!-- Code paths, configuration issues, infrastructure problems -->


### Contributing Factors
<!-- What made this worse or harder to detect? -->
- [ ] Missing monitoring
- [ ] Missing tests
- [ ] Configuration drift
- [ ] Other: ___

---

## 4. Fix

### Immediate Mitigation
<!-- What was done to stop the bleeding? -->


### Permanent Fix
<!-- What code/config changes were made? -->

| PR | SHA | Description |
|----|-----|-------------|
| #XXX | `abc1234` | Description |

---

## 5. Verification

### Pre-deploy Verification
| Check | Result | Evidence |
|-------|--------|----------|
| Unit tests pass | ✅/❌ | CI Run #XXX |
| Integration tests pass | ✅/❌ | CI Run #XXX |
| Security scan pass | ✅/❌ | CI Run #XXX |

### Post-deploy Verification
| Check | Result | Evidence |
|-------|--------|----------|
| Smoke gate pass | ✅/❌ | Deploy Run #XXX |
| Manual verification | ✅/❌ | Screenshot / curl output |
| Monitoring clean | ✅/❌ | Link to dashboard |

---

## 6. Prevention

### Immediate Actions (This Week)
- [ ] Action 1 — Owner: @username — Due: YYYY-MM-DD
- [ ] Action 2 — Owner: @username — Due: YYYY-MM-DD

### Long-term Improvements
- [ ] Add automated test for this scenario
- [ ] Add monitoring/alerting for this failure mode
- [ ] Update runbook
- [ ] Other: ___

---

## 7. Artifacts

### Deploy Run IDs
| Environment | Run ID | Status | Link |
|-------------|--------|--------|------|
| Staging | 123456 | ✅ | [Link](URL) |
| Production | 789012 | ✅ | [Link](URL) |

### Commit SHAs
| Commit | Description |
|--------|-------------|
| `abc1234` | Fix description |

### Related Documents
- [Link to related ADR]
- [Link to runbook]
- [Link to monitoring dashboard]

---

## 8. Rollback Plan

### If Issue Recurs
1. Revert commit `abc1234` with `git revert abc1234`
2. Push to main (requires PR if protected)
3. Deploy will auto-trigger
4. Verify smoke gate passes

### Emergency Bypass (Use Sparingly)
If smoke gate is failing but deploy is critical:
1. Add temporary allowlist entry to `docs/evidence/runtime_smoke_allowlist.json`
2. Commit with issue ID in message
3. Set expiry_date appropriately:
   - For status **503**: max 7 days
   - For status **500**: max 48 hours (strict policy)
4. For status **500**, you MUST also:
   - Include `KNOWN_BUG_TEMPORARY` in the `reason` field
   - Add `incident_doc` field pointing to `docs/evidence/INC-*.md`
5. Create follow-up issue immediately

**Expiry Interpretation**: Dates are UTC. Check is `TODAY > expiry_date` (expired if past).

---

## 9. Lessons Learned

### What Went Well
- 

### What Could Be Improved
- 

### Action Items from Retrospective
- [ ] Item 1
- [ ] Item 2

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | YYYY-MM-DD | @username | Initial creation |

---

**Review Required By**: @team-lead  
**Approved By**: _______________  
**Date**: _______________
