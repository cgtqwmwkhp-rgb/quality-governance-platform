# Change Ledger (CL-INV-C3-CANONICAL-READER)

> Adjacent, not fixed here: the detail page still *writes* flat keys (C4). Packs still render
> `data.sections` only (C13). This PR adds the rollback target those later PRs switch onto.

## 1) Summary
- **Feature / Change name:** INV-C3 — canonical reader for nested or flat investigation JSON
- **User goal:** Later writer and pack PRs must be able to roll back to a reader that understands both shapes. Today every caller guesses, which is why findings typed on the workspace never appear in the report.
- **In scope:** `read_investigation_field` / `read_investigation_section_field` — nested `data.sections` wins when both shapes exist; list-shaped sections are supported; empty string is preserved.
- **Out of scope:** Switching any writer (C4); backfill; pack content (C13); findings table (C7).
- **Feature flag / kill switch:** None. Kill SHA = LIVE `f65f8ecc2ef8`. No runtime caller yet, so revert is a no-op for users.

## 2) Impact Map (what changed)
- **Frontend:** none.
- **Backend:** new `src/domain/services/investigation_data_reader.py`.
- **APIs:** none. Nothing is wired to this reader yet.
- **Database / flags:** none.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive module. Existing readers are untouched.
- **Breaking changes:** none.
- **Migration plan:** none.
- **Rollback strategy (DB):** Revert the squash. No data migration.
- **Write-path safety:** This module does not write.

## Compliance Delta
- **PII touched?** No. The reader returns values already stored; it does not log them.
- **What this PR does not claim:** that the workspace and the pack now agree; that is C4 + C13.

## 4) Acceptance Criteria (AC)
- [x] AC-01: When a field exists both nested and flat, the nested section value is returned.
- [x] AC-02: When `sections` is absent, the top-level key is returned.
- [x] AC-03: List-shaped `sections` (`[{id, fields}]`) are read the same as the dict shape.
- [x] AC-04: Missing / malformed payloads and unknown fields return `None`.
- [x] AC-05: An explicit empty string is returned as empty string, not converted to `None`.
- [x] AC-06: `read_investigation_section_field` prefers the named section when two sections share a key.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_data_reader.py`.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: A from-record investigation (`data.sections.section_3_investigation_findings.findings`) and a workspace investigation (`data.findings`) are both readable without the caller knowing which shape it has.
- [x] CUJ-02: A leftover flat key cannot mask a nested value written later.

## 7) Observability & Ops
- **Logs:** none added.

## 8) Release Plan
- **Staging / prod:** no user-visible change. Confirm `/healthz` after deploy of the merge SHA.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** any caller introduced later that mis-reads a production payload.
- **Rollback steps:** Revert the squash on `main` and redeploy previous LIVE SHA `f65f8ecc2ef8`.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- No migration

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (new helper only; no contract change)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
