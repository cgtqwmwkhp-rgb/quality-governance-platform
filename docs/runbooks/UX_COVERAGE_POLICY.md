# UX Functional Coverage Policy

**Version:** 1.0  
**Last Updated:** 2026-01-26  
**Owner:** Platform Quality Team

---

## Purpose

This policy defines the UX Functional Coverage Gate requirements for the Quality Governance Platform. The gate ensures all user-facing functionality is tested before deployment to staging and production.

## Scope

The UX Coverage Gate validates:

1. **Page Load Audit** - All P0/P1 pages load successfully
2. **Link Audit** - All internal links resolve (no dead ends)
3. **Button Wiring Audit** - All P0/P1 buttons have observable outcomes
4. **Workflow Audit** - All P0 critical workflows complete end-to-end

## Registries

All audits are driven by YAML registries in `docs/ops/`:

| Registry | Purpose | Location |
|----------|---------|----------|
| PAGE_REGISTRY.yml | Routes, auth, criticality | docs/ops/PAGE_REGISTRY.yml |
| BUTTON_REGISTRY.yml | Actions, selectors, outcomes | docs/ops/BUTTON_REGISTRY.yml |
| WORKFLOW_REGISTRY.yml | End-to-end user journeys | docs/ops/WORKFLOW_REGISTRY.yml |

## Criticality Levels

| Level | Definition | Gate Behavior |
|-------|------------|---------------|
| **P0** | Critical path - must work for business continuity | Failure = HOLD (blocks all deployments) |
| **P1** | Important - should work for acceptable UX | Failure = -10 points per failure |
| **P2** | Nice to have - can degrade gracefully | Failure = -2 points per failure |

## Scoring

```
Score = 100 - (P1_failures × 10) - (P2_failures × 2)
```

**P0 failures bypass scoring** - Any P0 failure results in immediate HOLD regardless of score.

## Thresholds

| Environment | Min Score | Max P0 | Max P1 | Notes |
|-------------|-----------|--------|--------|-------|
| Staging Ready | 85 | 0 | - | Can deploy to staging for testing |
| Canary Expand | 90 | 0 | 3 | Can expand canary deployment |
| Production Promote | 95 | 0 | 1 | Can promote to full production |

## Gate Outcomes

| Status | Meaning | Action |
|--------|---------|--------|
| **GO** | All thresholds met for production | Proceed with deployment |
| **CANARY** | Staging/canary ready, not production | Deploy to canary only |
| **STAGING** | Staging ready, not canary/production | Deploy to staging only |
| **HOLD** | P0 failure or below staging threshold | Block deployment, investigate |

## Artifacts

The gate produces the following artifacts (retained 30 days):

| Artifact | Format | Purpose |
|----------|--------|---------|
| ux_coverage.json | JSON | Machine-readable results for Control Tower |
| ux_coverage.md | Markdown | Human-readable summary |
| ux_dead_end_map.md | Markdown | List of broken links and noop buttons |
| page_audit.json | JSON | Detailed page load results |
| link_audit.json | JSON | Detailed link audit results |
| button_audit.json | JSON | Detailed button wiring results |
| workflow_audit.json | JSON | Detailed workflow execution results |

## PII Safety

All audits are PII-safe:

- ❌ No real user credentials used (test tokens only)
- ❌ No form data captured in artifacts
- ❌ No screenshots with PII selectors
- ✅ Console logs sanitized (emails, phones redacted)
- ✅ Test data uses placeholders

## CI Integration

The UX Coverage Gate runs automatically:

1. **Trigger**: After staging deployment succeeds
2. **Workflow**: `.github/workflows/ux-functional-coverage.yml`
3. **Duration**: ~5-10 minutes
4. **Output**: Artifacts uploaded to workflow run

## Control Tower Integration

The `ux_coverage.json` artifact is ingested by Control Tower:

```javascript
// Added to control-tower.cjs
signals.ux = {
  score: ux_coverage.score,
  status: ux_coverage.status,
  p0_failures: ux_coverage.summary.p0_failures,
  p1_failures: ux_coverage.summary.p1_failures,
  dead_ends: ux_coverage.summary.dead_ends_count,
};

// Gate logic
if (signals.ux.p0_failures > 0) {
  go_no_go = 'HOLD';
  hold_reasons.push('UX P0 failure detected');
}
```

## Remediation Workflow

When the gate fails:

1. **Review ux_coverage.md** for failure summary
2. **Check ux_dead_end_map.md** for navigation issues
3. **Fix P0 issues immediately** (no workarounds)
4. **Log P1 issues** for next sprint if not immediately fixable
5. **Re-run gate** after fixes

## Registry Maintenance

**Adding new routes:**
```yaml
# In PAGE_REGISTRY.yml
- pageId: new-page
  route: /new-route
  auth: jwt_admin
  criticality: P1  # Start as P1, promote to P0 if critical
  component: NewPage
  expected_empty_state: "Expected empty state description"
  description: "What this page does"
```

**Adding new buttons:**
```yaml
# In BUTTON_REGISTRY.yml
- pageId: page-id
  actionId: button-action
  selector: "[data-testid='button-id']"  # Use data-testid!
  criticality: P1
  expected_outcome: navigation  # or network_call, ui_state
  expected_route: /target-route
  description: "What this button does"
```

## Selector Best Practices

1. **Always use data-testid** - Most stable selector
2. **Provide fallback_selector** - For graceful degradation
3. **Avoid text selectors** - They break with i18n
4. **Avoid class selectors** - They change with styling

```yaml
# Good
selector: "[data-testid='submit-btn']"
fallback_selector: "button[type='submit']"

# Bad
selector: ".btn-primary"
selector: "button:has-text('Submit')"
```

## Contact

- **Questions**: Platform Quality Team (#platform-quality)
- **Emergencies**: Page on-call SRE
- **Registry Updates**: Submit PR with test evidence

---

*This policy is enforced by the CI pipeline. Exceptions require VP approval and documented waiver.*
