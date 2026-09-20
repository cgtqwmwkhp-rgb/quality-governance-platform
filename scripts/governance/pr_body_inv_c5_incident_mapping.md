# Change Ledger (CL-INV-C5-INCIDENT-MAPPING)

> Adjacent, not fixed here: `source_snapshot` is still omitted from the API and the Summary card
> still renders `investigation.description` (C5 snapshot / UI, needs InvestigationDetail after C2).
> This PR only completes `map_source_to_investigation` for `reporting_incident`.

## 1) Summary
- **Feature / Change name:** INV-C5 — incident create-from-record copies the same field set as near miss
- **User goal:** Opening an investigation from an incident should not force retyping of people involved, witnesses, immediate actions, severity, or injury detail. Near miss and RTA already mapped those; incident mapped four fields.
- **In scope:** `REPORTING_INCIDENT` mapping adds people, witnesses, severity, department, injury flags, and immediate-action fields into `data.sections`. Enum values are stored as their `.value`.
- **Out of scope:** Exposing `source_snapshot` on the API; Summary UI; rewriting already-open investigations; nested writer (C4).
- **Feature flag / kill switch:** None. Kill SHA = LIVE `f65f8ecc2ef8`.

## 2) Impact Map (what changed)
- **Frontend:** none.
- **Backend:** `InvestigationService.map_source_to_investigation` for `reporting_incident`.
- **APIs:** none. Same create-from-record endpoint; the nested `data` payload is richer for new incident investigations.
- **Database / flags:** none. Existing JSON column.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive keys inside `data.sections`. Existing investigations are not rewritten. Identity fields land on `persons_involved` / `witnesses`, which the external pack already redacts.
- **Breaking changes:** none.
- **Migration plan:** none. Already-open incident investigations keep the four-field snapshot.
- **Rollback strategy (DB):** Revert the squash. Rows created under this PR keep the extra keys (harmless).
- **Write-path safety:** `people_involved` is mapped onto `persons_involved` so the pack identity allow-list covers it. No PAMS write.

## Compliance Delta
- **PII touched?** Names already stored on the incident are copied into the investigation JSON, as near miss already did. External packs still redact `persons_involved` and `witnesses`.
- **What this PR does not claim:** that the Summary card shows the snapshot; that old investigations are backfilled.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Incident mapping copies people involved, witnesses, severity, department, injury detail, and immediate actions into the nested sections.
- [x] AC-02: `IncidentSeverity` is stored as `"high"` (the enum value), not the enum object.
- [x] AC-03: The original four fields (reference, date, location, description) still copy.
- [x] AC-04: Missing people / witnesses stay `None` rather than inventing a string.
- [x] AC-05: Suggested investigation level from severity is unchanged.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_incident_mapping.py`.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open investigation from an injury incident that has people, witnesses, immediate actions and LTI flags. Those values are in `data.sections` without retyping.
- [x] CUJ-02: An incident with only the original four fields still maps those four; extra keys are present as null/false rather than omitted-and-lost.

## 7) Observability & Ops
- **Logs:** mapping_log gains extra SUCCESS / FALLBACK rows for the new fields.

## 8) Release Plan
- **Staging:** Create-from-record on a sandbox incident with people/actions/injury filled. GET the investigation and confirm nested keys.
- **Prod post-deploy:** `/healthz`; `/api/v1/meta/version` `build_sha` == tip. Do not reopen a live investigation to test.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** create-from-record 500s; identity fields landing under names the pack does not redact.
- **Rollback steps:** Revert the squash on `main` and redeploy previous LIVE SHA `f65f8ecc2ef8`.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- No migration

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (additive nested keys; pack identity names reused)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
