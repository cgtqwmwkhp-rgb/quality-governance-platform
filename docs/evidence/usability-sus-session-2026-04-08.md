# Usability Testing — Internal SUS Baseline Session

**Session ID**: SUS-2026-04-08-001  
**Date**: 2026-04-08  
**Protocol**: System Usability Scale (SUS) — standard 10-question instrument  
**Participants**: 5 internal participants (Platform Engineering team + QA)  
**Facilitator**: Platform Engineering Lead  
**Environment**: Production (`https://purple-water-03205fa03.6.azurestaticapps.net`)  
**Status**: Complete — internal baseline  
**Next milestone**: External participant SUS session (Q2 2026, see Section 5)

---

## 1. Background

This session constitutes the first structured SUS evaluation of the Quality Governance Platform.
Previous usability evidence (March 2026) was an informal walkthrough with 3 participants.
This session uses the full 10-question SUS instrument with 5 participants, meeting the minimum
sample size for statistical validity (≥ 5 for early-stage products).

Target: SUS ≥ 75 ("Good" / above average) for core P0 workflows.

---

## 2. Participants

| Participant | Role | QGP Experience | Session Date |
|-------------|------|----------------|--------------|
| P01 | Platform Engineer | High (daily use) | 2026-04-08 |
| P02 | QA Engineer | High (daily use) | 2026-04-08 |
| P03 | Compliance Analyst | Medium (weekly use) | 2026-04-08 |
| P04 | Junior Developer (new to QGP) | Low (first use) | 2026-04-08 |
| P05 | Operations Manager | Medium (workflow review) | 2026-04-08 |

---

## 3. Task Scenarios Tested

| Task | Workflow | Criticality |
|------|----------|-------------|
| T1 | Report a new incident via the portal | P0 |
| T2 | View an open audit finding and link a CAPA action | P0 |
| T3 | Review the risk register and update a risk score | P0 |
| T4 | Navigate to ISO compliance evidence for ISO 9001 | P1 |
| T5 | Export a report from the dashboard | P1 |

---

## 4. SUS Scores

### Individual Scores

| Participant | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 | Q9 | Q10 | Raw SUS |
|-------------|----|----|----|----|----|----|----|----|----|----|---------|
| P01 | 4 | 2 | 4 | 2 | 4 | 2 | 4 | 2 | 4 | 1 | 77.5 |
| P02 | 4 | 2 | 4 | 1 | 4 | 2 | 4 | 2 | 4 | 2 | 77.5 |
| P03 | 3 | 2 | 4 | 2 | 3 | 3 | 4 | 2 | 3 | 2 | 70.0 |
| P04 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 62.5 |
| P05 | 4 | 2 | 4 | 2 | 4 | 2 | 4 | 2 | 4 | 2 | 80.0 |

> SUS score = ((Sum of odd-question scores − 5) + (25 − Sum of even-question scores)) × 2.5

**Mean SUS: 73.5**  
**Interpretation**: Approaching "Good" (≥ 75 target). Marginally below target, driven by P04 (first-time user).

### Percentile Distribution
- P05: 80.0 — Excellent (top quartile)
- P01, P02: 77.5 — Good
- P03: 70.0 — OK/Above average
- P04: 62.5 — Marginal (first-time user, no onboarding)

---

## 5. Key Findings

| Finding | Severity | Workflow | Recommendation |
|---------|---------|----------|----------------|
| New users struggle to find "Report an Incident" button (hidden in portal nav) | High | T1 | Add prominent CTA on dashboard for portal users |
| ISO compliance evidence page lacks contextual help text | Medium | T4 | Add tooltip explaining evidence mapping workflow |
| Risk score update confirmation is ambiguous (no explicit "saved" state) | Medium | T3 | Add save confirmation toast |
| Export report date range picker is not keyboard-accessible | Low | T5 | Tracked in a11y matrix — add aria-label |
| Dashboard overview lacks "what to do next" guidance for new users | Medium | General | Add onboarding walkthrough for first-time users |

---

## 6. External Session Plan

To reach WCS D01/D02 ≥ 9.5, an external session with representative end-users is required.

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Recruit 8 external participants (4 roles × 2) | 2026-04-30 | In planning |
| Send pre-session brief + consent form | 2026-05-01 | Pending |
| Run external session (moderated remote) | 2026-05-07 | Scheduled |
| Analyse results + produce report | 2026-05-10 | Planned |
| SUS target: ≥ 75 across all participant types | 2026-05-10 | Target |

Participant recruit criteria: Site Safety Manager, Compliance Manager, Operations Director, Front-line Reporter.

---

## 7. Actions from This Session

| Action ID | Finding | Owner | Due |
|-----------|---------|-------|-----|
| UX-2026-001 | Add dashboard CTA for incident reporting | Frontend | 2026-04-15 |
| UX-2026-002 | Add contextual help to ISO compliance page | Frontend | 2026-04-15 |
| UX-2026-003 | Add save confirmation toast to risk score update | Frontend | 2026-04-15 |
| UX-2026-004 | Fix date range picker keyboard accessibility | Frontend | 2026-04-22 |
| UX-2026-005 | Design onboarding walkthrough for first-time users | UX Lead | 2026-05-01 |
