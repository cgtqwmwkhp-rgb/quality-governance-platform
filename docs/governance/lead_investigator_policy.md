# Lead Investigator person-mode policy

**Programme:** People+Preview (Lane P-Owners)  
**Status:** Locked — do not “hybrid-ise” the incident closure lead

## Policy (split by surface)

| Surface | Field | Mode | Control |
|---------|--------|------|---------|
| `IncidentDetail` investigation create | `lead_investigator` | **employeesOnly** | `EngineerPeoplePicker` with `requireLogin={true}` |
| `InvestigationDetail` summary | `summaryLead` → `lead_investigator` | **hybrid** | `EngineerPeoplePicker` with `requireLogin={false}` |

### Why the split

1. **IncidentDetail (employeesOnly)** — Incident closure gates require a linked QGP user for the lead investigator (`LEAD_INVESTIGATOR_NOT_ASSIGNED` / accountable assignee). Free-text or roster-only names without a login must not satisfy this path.
2. **InvestigationDetail (hybrid)** — Retains PX-168 behaviour: roster-only names may be stored via `assignee_name` when the person has no QGP login. Do not tighten this to `requireLogin={true}` without an explicit product decision.

### Agent / PR guardrail

Future People+Preview work must **not** change IncidentDetail `lead_investigator` to hybrid/`requireLogin={false}` in the name of “parity”. CAPA assignees on Incident/Complaint/Near Miss/RTA/ActionDetail remain **employeesOnly** (`requireLogin={true}`).
