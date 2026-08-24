# Change Ledger (CL-LIB-F4-ADR-0023)

## 1) Summary
- **Feature / Change name:** Library F-4 (+ F-5 / F-6 / F-7) — ADR-0023 PEL scheme + clause/CEL/home design pack
- **User goal (1–2 lines):** Publish the Governance Library function-axis reference scheme under the correct ADR number (0023, not 0020), and lock D14/D15/F-7 dispositions as docs so SECOND waves enhance existing SoTs instead of inventing twins.
- **In scope:** `docs/adr/ADR-0023-governance-library-reference-scheme.md`; cross-links on ADR-0021 / ADR-0022; F-5 D14 clause identity note; F-6 D15 CEL harden note; F-7 home inventory; brief pointer in `specs/governance-library/README.md`; this Change Ledger
- **Out of scope:** `documents.py` / `file_validation`; alembic; `functions.json` seed (WA-2); CEL/schema code (WI-1); enabling Doc Graph / job_lifecycle flags; Citation cutover
- **Feature flag / kill switch:** N/A (docs-only)

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** None
- **APIs:** None
- **Database:** None
- **Config/env/flags:** None
- **Dependencies:** None
- **Tests:** None (docs-only)
- **Docs:** New ADR-0023; D14/D15/F-7 governance notes; ADR-0021/0022 + spec README cross-links

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Documentation only; runtime PEL allocation remains category-derived until WA-2 implements ADR-0023
- **Breaking changes:** None
- **Migration plan:** N/A this PR — WI-1 / WA-2 / WI-2 / CUT-1 own schema moves described in the notes
- **Rollback strategy (DB):** N/A — revert commit / supersede ADR status if product reverses

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Library PEL ADR numbering | WIP / Downloads falsely used ADR-0020; conflict with Compliance Schedule ADR-0020 | ADR-0023 published; ADR-0020 reserved for occurrence model |
| Function vs category reference | Category-derived `PEL-<SECTION>-<SUB>-<SEQ>` live; function scheme undecided in-repo | ADR-0023 Accepted: `PEL-<FUNCTION>-<SEQ>`; category classifies |
| ISO clause identity | `ALL_CLAUSES` strings vs `clauses.id` int — unjoinable | D14: converge via `clauses.catalogue_key`; no second standards library |
| Coverage SoT | Risk of inventing `document_coverage_claims` | D15: harden CEL only (soft-delete unique, `cover_kind`, `confirmed_by`) |
| Multi-home file/retention/access | Parallel homes known but undisposed | F-7 keep\|migrate\|drop tables for implementers |
| Doc Graph / JL SSOT discipline | ADR-0021 / 0022 silent on library PEL | Cross-linked; function codes ≠ edges ≠ lanes |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `docs/adr/ADR-0023-governance-library-reference-scheme.md` exists; Status Accepted; title is library PEL / filing rules
- [x] AC-02: ADR body states ADR-0020 is Compliance Schedule and must not be used for this scheme
- [x] AC-03: ADR-0023 cross-links ADR-0021 and ADR-0022; those ADRs link back
- [x] AC-04: No new `docs/adr/ADR-0020-governance-library-*` on this branch; tip `main` retains compliance-schedule ADR-0020 only
- [x] AC-05: D14 note recommends `catalogue_key` convergence; forbids frameworks / coverage_claims twins
- [x] AC-06: D15 note specifies soft-delete-aware unique, `cover_kind` covers\|evidences, `confirmed_by`; never `document_coverage_claims`
- [x] AC-07: F-7 disposition tables cover file, retention, and access multi-homes with keep\|migrate\|drop
- [x] AC-08: Diff is docs (+ this ledger) only — no app / alembic / `documents.py` / `file_validation`

## 5) Testing Evidence (link to runs)
- [ ] Lint / markdown — CI as applicable
- [x] Diff review — docs/adr + docs/governance + specs README + Change Ledger only
- [ ] Unit / Integration / Contract / E2E — N/A docs-only

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Reader asking for “library PEL ADR” finds **ADR-0023**, not ADR-0020
- [x] CUJ-02: Reader asking “do we build coverage_claims?” → No — harden CEL (D15)
- [x] CUJ-03: Reader asking “which clause id?” → catalogue string converging onto `clauses.catalogue_key` (D14)
- [x] CUJ-04: Implementer of WI-2 / CUT-1 has keep\|migrate\|drop guidance (F-7)

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** None
- **Runbook updates:** None — Function allocator change is WA-2; CEL harden is WI-1

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging / Prod:** Docs ship with tip; no flag flips; no behavioural bake
- **Canary plan:** N/A
- **DONE bar:** Conveyor marks F-4…F-7 PROD/DONE only after tip SHA is LIVE (merge alone is insufficient)

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Product reverses function-axis PEL or wants a new coverage table before WI-1
- **Rollback steps:** Supersede ADR-0023 / design notes with a follow-on ADR (do not silently contradict); revert this commit if files must leave `main`
- **Owner:** Platform Engineering (Library spine) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: N/A docs-only (tip chase follows normal main deploy)
- Canary evidence (if applicable): N/A
- Source content (Downloads WIP, renumbered): `ADR-0020-governance-library-reference-scheme_1.md` → published as ADR-0023

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (design lock only; no API this PR)
- [ ] **Gate 2:** CI green (lint/type/build/tests as applicable)
- [x] **Gate 3:** Staging verification complete (evidence linked) — N/A docs-only pre-merge
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — tip SHA after merge; no flag enablement
