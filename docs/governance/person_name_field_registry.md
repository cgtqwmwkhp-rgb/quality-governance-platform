# Person Name Field Registry (SSOT)

**Programme:** People+Preview  
**Investigator:** INV-A  
**Branch:** `feat/people-preview-registries`  
**Generated:** 2026-08-06  
**Scope:** Every frontend person/name input surface in `frontend/src`, with obvious backend field mappings where found.

## Legend

| Column | Meaning |
|--------|---------|
| **Control** | Current UI widget |
| **Desired mode** | Target People+Preview behaviour |
| **Portal / Admin** | Surface audience |
| **Priority** | P0 incident person involved & witnesses; P1 NM/Complaint/RTA person fields; P2 owners/assignees; P3 other |

**Desired modes**

- **hybrid** — employee lookup (PAMS roster / QGP user) plus free-text fallback
- **employeesOnly** — must resolve to a known employee/user (login required where assignment depends on it)
- **freeTextOnly** — external or unknown persons; lookup would block valid intake

---

## Summary

| Priority | Count |
|----------|------:|
| P0 | 9 |
| P1 | 16 |
| P2 | 15 |
| P3 | 5 |
| **Total surfaces** | **45** |

Shared component note: `CaseWitnessesPanel` (`witness.name`) is one component used on four case detail pages — counted once in the total, with consumers listed.

---

## P0 — Incident person involved & witnesses

| # | File / symbol | Label / form key / API | Control | Desired mode | Portal / Admin | Justification |
|---|---------------|------------------------|---------|--------------|----------------|---------------|
| 1 | `frontend/src/pages/PortalIncidentForm.tsx` — `personName` | Label: "Your name" / "Person involved name"; keys: `personName` → `reporter_submission.person_name`, `reporter_name` | Plain `Input` | **hybrid** | Portal | Reporters are usually employees but field captures whoever was involved; prefill from session name only |
| 2 | `frontend/src/pages/PortalIncidentForm.tsx` — `witnessNames` | Label: "Witness names"; keys: `witnessNames` → `reporter_submission.witness_names` | Plain `Textarea` | **freeTextOnly** | Portal | Witnesses are often customers, public, or third parties outside PAMS |
| 3 | `frontend/src/pages/PortalDynamicForm.tsx` — incident template field `person_name` | Label: "Full Name"; key: `person_name` → `reporter_name` | `DynamicFormRenderer` → `Input` (text) | **hybrid** | Portal | Fallback incident template; same semantics as `PortalIncidentForm` |
| 4 | `frontend/src/pages/PortalDynamicForm.tsx` — incident template field `witness_names` | Label: "Witness Names"; key: `witness_names` | `DynamicFormRenderer` → `Textarea` | **freeTextOnly** | Portal | Multi-witness free text at intake |
| 5 | `frontend/src/pages/PortalNearMissForm.tsx` — `witnessNames` | Label: "Any witnesses?" detail; keys: `witnessNames` → `reporter_submission.witness_names` | Plain `Textarea` | **freeTextOnly** | Portal | Portal NM witness capture is unstructured contact text |
| 6 | `frontend/src/pages/PortalRTAForm.tsx` — `witnessDetails` | Label: witness contact; keys: `witnessDetails` → `reporter_submission.witness_details` → backend `witnesses_structured.witnesses[].name` | Plain `Textarea` | **freeTextOnly** | Portal | RTA witnesses frequently external; backend wraps as single free-text witness row |
| 7 | `frontend/src/pages/IncidentDetail.tsx` — `editForm.people_involved` | Label: "Person involved"; API: `people_involved` (`IncidentUpdate`) | Plain `Input` | **hybrid** | Admin | Ops may correct portal free text or link to employee; field is varchar not FK |
| 8 | `frontend/src/components/case/CaseWitnessesPanel.tsx` — `witness.name` | Label: "Name"; API: `witnesses_structured.witnesses[].name` | Plain `Input` (per witness row) | **freeTextOnly** | Admin | Structured witness editor; consumers: `IncidentDetail`, `NearMissDetail`, `ComplaintDetail` (`testIdPrefix`: incident / near-miss / complaint) |
| 9 | `frontend/src/pages/RTADetail.tsx` — inline `editWitnesses[].name` | Label: "Name"; API: `witnesses_structured.witnesses[].name` | Plain `Input` (inline editor, not `CaseWitnessesPanel`) | **freeTextOnly** | Admin | RTA detail uses bespoke witness editor; same schema as panel |

**Backend (P0-related):**

- `src/api/schemas/incident.py`: `people_involved`, `witnesses_structured`
- `src/api/schemas/near_miss.py`, `complaint.py`, `rta.py`: `witnesses_structured`
- `src/api/routes/employee_portal.py`: maps portal `person_name`, `witness_names`, `witness_details` into case records

---

## P1 — Near miss, complaint, RTA person fields

| # | File / symbol | Label / form key / API | Control | Desired mode | Portal / Admin | Justification |
|---|---------------|------------------------|---------|--------------|----------------|---------------|
| 10 | `frontend/src/pages/PortalIncidentForm.tsx` — `complainantName` | Label: "Complainant name"; keys: `complainantName` → `reporter_submission.complainant_name`, `reporter_name` | Plain `Input` | **freeTextOnly** | Portal | Customer / external complainant, not workforce roster |
| 11 | `frontend/src/pages/PortalDynamicForm.tsx` — complaint template `complainant_name` | Label: "Complainant Name"; key: `complainant_name` | `DynamicFormRenderer` → `Input` | **freeTextOnly** | Portal | Complaint fallback template |
| 12 | `frontend/src/pages/PortalNearMissForm.tsx` — `reporterName` | Label: "Your name"; keys: `reporterName` → `reporter_name` | Plain `Input` | **hybrid** | Portal | NM reporter usually employee; must allow proxy reporting |
| 13 | `frontend/src/pages/PortalNearMissForm.tsx` — `personsInvolved` | Label: "Others involved"; key: `persons_involved` in submission | Plain `Input` | **freeTextOnly** | Portal | Free-text list of other parties at NM intake |
| 14 | `frontend/src/pages/PortalRTAForm.tsx` — `employeeName` | Label: "Your name"; keys: `employeeName` → `reporter_name`, `driver_name`, `employee_name` | Plain `Input` | **hybrid** | Portal | Our driver/reporter is usually employee; portal allows manual entry |
| 15 | `frontend/src/pages/PortalRTAForm.tsx` — `thirdParties[].driverName` | Label: third-party driver; key: `third_parties[].name` in submission | Plain `Input` (repeatable) | **freeTextOnly** | Portal | Other motorists are external by definition |
| 16 | `frontend/src/pages/NearMisses.tsx` — create `reporter_name` | Label: "Reporter name"; API: `reporter_name` | Plain `Input` | **hybrid** | Admin | Admin-created NM; reporter may be employee or typed name |
| 17 | `frontend/src/pages/Complaints.tsx` — create `complainant_name` | Label: "Complainant name"; API: `complainant_name` | Plain `Input` | **freeTextOnly** | Admin | External complainant identity |
| 18 | `frontend/src/pages/Complaints.tsx` — `subject_name` + `EngineerPeoplePicker` | Labels: "Who is the complaint about (staff)" / "About (name if not a staff user)"; API: `subject_name`, `subject_user_id` | `EngineerPeoplePicker` (`requireLogin=false`) + fallback `Input` | **hybrid** | Admin | Subject may be roster employee or external person named in complaint |
| 19 | `frontend/src/pages/ComplaintDetail.tsx` — `editForm.complainant_name` | Label: complainant info; API: `complainant_name` | Plain `Input` | **freeTextOnly** | Admin | Edit external complainant record |
| 20 | `frontend/src/pages/RTAs.tsx` — create `driver_name` | Label: driver name; API: `driver_name` | Plain `Input` | **hybrid** | Admin | Our driver usually employee; admin may enter before link exists |
| 21 | `frontend/src/pages/RTAs.tsx` — create `reporter_name` | Label: "Reporter name"; API: `reporter_name` | Plain `Input` | **hybrid** | Admin | Reporter distinct from driver; may differ from session |
| 22 | `frontend/src/pages/RTADetail.tsx` — `editForm.driver_name` | Label: "Driver Name" (Our Driver tab); API: `driver_name` | Plain `Input` | **hybrid** | Admin | Ops correction of our driver identity |
| 23 | `frontend/src/pages/RTADetail.tsx` — `editThirdParties[].name` | Label: "Name" (Other Driver tab); API: `third_parties` JSON | Plain `Input` | **freeTextOnly** | Admin | Third-party drivers are external |
| 24 | `frontend/src/pages/NearMissDetail.tsx` — `reporter_name` | Display only in summary (no edit control) | Read-only | **hybrid** (future) | Admin | No input today; listed for completeness — reporter shown from API |
| 25 | `frontend/src/pages/IncidentDetail.tsx` — `reporter_name` | Display only in overview | Read-only | **hybrid** (future) | Admin | No edit input; captured at portal/create time |

**Backend (P1-related):**

- `src/api/schemas/near_miss.py`: `reporter_name`
- `src/api/schemas/complaint.py`: `complainant_name`, `subject_name`, `subject_user_id`
- `src/api/schemas/rta.py`: `driver_name`, `reporter_name`, `third_parties`
- `src/api/routes/employee_portal.py`: `reporter_name`, `complainant_name` aliases

---

## P2 — Owners, assignees, lead investigator

| # | File / symbol | Label / form key / API | Control | Desired mode | Portal / Admin | Justification |
|---|---------------|------------------------|---------|--------------|----------------|---------------|
| 26 | `frontend/src/pages/Incidents.tsx` — register owner triage | Placeholder: "Search active employees…"; API: `owner_id` | `EngineerPeoplePicker` (`requireLogin=true`) | **employeesOnly** | Admin | Case owner must be linked QGP user for assignment workflow |
| 27 | `frontend/src/pages/Complaints.tsx` — register owner triage | Same pattern; API: `owner_id` | `EngineerPeoplePicker` (`requireLogin=true`) | **employeesOnly** | Admin | Portal intakes need accountable internal owner |
| 28 | `frontend/src/pages/IncidentDetail.tsx` — investigation `lead_investigator` | Label: "Lead investigator"; API: investigation `lead_investigator` | `EngineerPeoplePicker` (`requireLogin=true`) | **employeesOnly** | Admin | Closure gate `LEAD_INVESTIGATOR_NOT_ASSIGNED`; needs accountable user |
| 29 | `frontend/src/pages/IncidentDetail.tsx` — CAPA action assignee | Label: "Assign to"; API: action `assigned_to` / owner email | `EngineerPeoplePicker` (`requireLogin=true`) | **employeesOnly** | Admin | Action ownership requires login for notifications |
| 30 | `frontend/src/pages/ComplaintDetail.tsx` — CAPA action assignee | Label: "Assign to" | `EngineerPeoplePicker` (`requireLogin=true`) | **employeesOnly** | Admin | Same as incident actions |
| 31 | `frontend/src/pages/NearMissDetail.tsx` — CAPA action assignee | Label: "Assign to" | `UserEmailSearch` | **employeesOnly** | Admin | Email/user search — QGP users only |
| 32 | `frontend/src/pages/RTADetail.tsx` — CAPA action assignee | Label: "Assign to" | `UserEmailSearch` | **employeesOnly** | Admin | Same pattern as near miss |
| 33 | `frontend/src/pages/InvestigationDetail.tsx` — `summaryLead` | Label: "Lead investigator"; API: `lead_investigator` | `EngineerPeoplePicker` (`requireLogin=false`) | **hybrid** | Admin | Supports roster-only name via `assignee_name` when no login (`employeePickerUtils`) |
| 34 | `frontend/src/pages/investigation/InvestigationActions.tsx` — action assignee | Label: "Assign To"; API: `assignee_id`, `assignee_email`, `assignee_name` | `EngineerPeoplePicker` (`requireLogin=false`) | **hybrid** | Admin | PX-168: roster-only assignee name allowed |
| 35 | `frontend/src/pages/Investigations.tsx` — modal action assignee | Label: "Assign To" | `UserEmailSearch` | **employeesOnly** | Admin | Legacy investigations list modal |
| 36 | `frontend/src/pages/ActionDetail.tsx` — `assigneeDraft` | Label: "Assignee owner responsible"; API: `assigned_to_email` / `owner_email` | Plain `Input` (email text) | **employeesOnly** | Admin | Free-text email entry but must resolve to platform user on save |
| 37 | `frontend/src/pages/RiskRegister.tsx` — accept dialog owner | Label: "Owner" | `UserEmailSearch` | **employeesOnly** | Admin | Accept blocked until owner assigned (`canAcceptImportTriage`) |
| 38 | `frontend/src/pages/RiskRegister.tsx` — detail `ownerDraft` | Label: "Owner name"; API: `risk_owner_name` | Plain `Input` | **hybrid** | Admin | Import triage allows typed owner name before user link |
| 39 | `frontend/src/pages/RiskProfile.tsx` — owner picker | API: `risk_owner_id`, `risk_owner_name` | `UserEmailSearch` | **employeesOnly** | Admin | Profile owner is a platform user |
| 40 | `frontend/src/pages/compliance/RequirementFormDialog.tsx` — owner | Label: "Owner" | `UserEmailSearch` | **employeesOnly** | Admin | Compliance schedule requirement owner |

**Backend (P2-related):**

- `src/api/schemas/investigation.py`: `assignee_id`, `assignee_email`, `assignee_name`
- `src/api/schemas/incident.py` / complaints / near_misses / rtas: `owner_id`
- `src/api/schemas/risk_register.py` (via client): `risk_owner_id`, `risk_owner_name`

---

## P3 — Other person/name inputs

| # | File / symbol | Label / form key / API | Control | Desired mode | Portal / Admin | Justification |
|---|---------------|------------------------|---------|--------------|----------------|---------------|
| 41 | `frontend/src/pages/admin/UserManagement.tsx` — `first_name`, `last_name` | User account names; API: user create/update | Plain `Input` | **freeTextOnly** | Admin | Platform identity admin, not case person registry |
| 42 | `frontend/src/pages/workforce/Engineers.tsx` — create `display_name` | PAMS roster display name | Plain `Input` | **freeTextOnly** | Admin | Workforce master data, source of truth for picker labels |
| 43 | `frontend/src/pages/workforce/EngineerProfile.tsx` — edit `display_name` | PAMS roster display name | Plain `Input` | **freeTextOnly** | Admin | Roster maintenance |
| 44 | `frontend/src/pages/audit-builder/EntitySelectAnswer.tsx` — `UserEntitySelect` | Audit answer user entity; stores user id + `display_name`/`full_name` label | Combobox search (`usersApi.search`) | **employeesOnly** | Admin | Audit questions selecting a QGP user |
| 45 | `frontend/src/components/UserEmailSearch.tsx` | Reusable email/name search (used outside P2 surfaces in engineer link flows) | Combobox (`Engineers.tsx`, `EngineerProfile.tsx` link-to-user) | **employeesOnly** | Admin | Links PAMS engineer to QGP login — not a case person field |

---

## Component reference

### `EngineerPeoplePicker`

Path: `frontend/src/components/EngineerPeoplePicker.tsx`

- Lists active PAMS engineers; optional QGP login requirement via `requireLogin`
- Used on: incident/complaint owner triage, incident/complaint/investigation assignees, complaint subject, lead investigator surfaces (see P1/P2 tables)
- Resolution helper: `frontend/src/pages/workforce/employeePickerUtils.ts` → `resolveInvestigationAssigneeSelection`

### `CaseWitnessesPanel`

Path: `frontend/src/components/case/CaseWitnessesPanel.tsx`

- Structured multi-witness editor; `witness.name` is plain `Input`
- Consumed by: `IncidentDetail`, `NearMissDetail`, `ComplaintDetail`
- **Not** used by `RTADetail` (inline editor instead)

### `UserEmailSearch`

Path: `frontend/src/components/UserEmailSearch.tsx`

- QGP user search by email/name; no free-text name persistence without user match
- Used for assignees, risk owners, compliance owners, engineer linking

### `DynamicFormRenderer`

Path: `frontend/src/components/DynamicForm/DynamicFormRenderer.tsx`

- Renders configurable form templates as plain `Input`/`Textarea` for text fields
- Portal person fields defined in `PortalDynamicForm.tsx` `PORTAL_FORM_TEMPLATES` (incident, complaint; near-miss template has no person_name fields)

---

## Top P0 list (implementation order)

1. **`PortalIncidentForm` — `personName`** → `person_name` / `reporter_name` — highest-volume portal incident intake
2. **`IncidentDetail` — `people_involved`** — admin correction of person involved on live incidents
3. **`CaseWitnessesPanel` — `witness.name`** — shared structured witness editor (incident, near miss, complaint)
4. **`PortalIncidentForm` — `witnessNames`** — portal incident witness free text
5. **`PortalDynamicForm` — `person_name` + `witness_names`** — fallback template path when legacy dynamic route used
6. **`PortalNearMissForm` — `witnessNames`** — NM portal witnesses
7. **`PortalRTAForm` — `witnessDetails`** — RTA portal witnesses (backend normalizes to structured)
8. **`RTADetail` — inline `editWitnesses[].name`** — RTA admin witness parity with panel

---

## Gaps / notes

- **Reporter fields** on incident/near-miss detail pages are display-only today (no admin edit surface).
- **Near-miss dynamic template** in `PortalDynamicForm` omits `person_name` / witness fields — dedicated `PortalNearMissForm` covers NM intake.
- **RTA dynamic template** omits driver/witness name fields — `PortalRTAForm` is the primary RTA intake.
- **No dedicated `person` field type** in `DynamicFormRenderer`; all person names render as generic text inputs.
- **`EngineerPeoplePicker`** is the only workforce-aware person control; no shared hybrid picker exists yet for P0/P1 intake fields.
