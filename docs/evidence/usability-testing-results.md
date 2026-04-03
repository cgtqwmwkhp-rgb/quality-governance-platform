# Usability Testing Results (D01)

Baseline framework for usability testing of the Quality Governance Platform.

## System Usability Scale (SUS) Framework

The [System Usability Scale](https://www.usability.gov/how-to-and-tools/methods/system-usability-scale.html) is a 10-item questionnaire yielding a score from 0–100.

| Rating | SUS Score | Interpretation |
|--------|-----------|----------------|
| Excellent | >= 80 | Top quartile usability |
| Good | 68–79 | Above average |
| OK | 50–67 | Marginal acceptability |
| Poor | < 50 | Below acceptable |

**Target**: SUS >= 75 (Good) for core workflows.

## Core Workflows Under Test

| # | Workflow | Priority | Status |
|---|----------|----------|--------|
| 1 | Report an incident | P0 | Framework ready |
| 2 | Import an external audit (UVDB) | P0 | Framework ready |
| 3 | View and manage findings | P0 | Framework ready |
| 4 | Create and track CAPA actions | P0 | Framework ready |
| 5 | View enterprise risk register | P1 | Framework ready |
| 6 | Manage complaints | P1 | Framework ready |
| 7 | Run an investigation | P1 | Framework ready |
| 8 | Dashboard overview | P1 | Framework ready |

## Test Session Template

### Pre-Test
- Participant demographics (role, experience level)
- Task scenario description (written, not verbal)
- Environment: production-like staging URL

### During Test
- Task completion rate (binary: completed / not completed)
- Time on task (seconds)
- Error count (wrong clicks, navigation confusion)
- Think-aloud notes

### Post-Test
- SUS questionnaire (10 items)
- Open-ended feedback: "What was most confusing?" / "What worked well?"

## Baseline Results

| Session | Date | Participants | Avg SUS | Top Issue |
|---------|------|--------------|---------|-----------|
| Round 1 | TBD | TBD | TBD | TBD |

Results will be populated after the first usability testing round is conducted.

## Related Documents

- [`docs/ux/ux-style-guide.md`](../ux/ux-style-guide.md) — UX standards
- [`frontend/src/components/`](../../frontend/src/components/) — component library
