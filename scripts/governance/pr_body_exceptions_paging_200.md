# Change Ledger (CL-EXCEPTIONS-PAGING-200)

> **Start gate:** #1786 LIVE @ `d94732fe8a6a`. `STACK_MAX=1`. Merge ≠ LIVE.
> David lock 2026-08-18: real next/prev, keep 200 rows per page, named truncation. Do not raise the cap.
> Entra flag stays false in this PR (dedicated `ENTRA_ATTESTATION_*` settings are not on STG/PROD).

## 1) Summary
- **Feature / Change name:** Exceptions inbox paging (200/page)
- **User goal:** Walk the full proposed-share inbox without a silent dump. Each page is at most 200 rows and says so.
- **In scope:** `GET /api/v1/knowledge-bank/exceptions` page envelope + FE Previous/Next. Cap stays 200.
- **Out of scope:** Raising the cap. Totals. Entra flag. S4 trees. Scheme EXACT. Assist triad. Dependabot.
- **Feature flag / kill switch:** None. Revert this PR. Inbox still functions as page 1 of up to 200.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| EX-P-01 | `GET /knowledge-bank/exceptions` | Bare list, SQL `.limit(200)` | Envelope `{items,page,page_size,truncated,has_next,has_prev}` with `page`/`page_size` (max 200) |
| EX-P-02 | Exceptions FE | One truncated page | Previous/Next. Honesty names page of up to 200. URL `page=` |
| EX-P-03 | Tolerant reader | List only | FE unwraps envelope or legacy array |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** FE unwraps a list or an envelope. Default `page=1`, `page_size=200` matches the old first page.
- **Breaking changes:** API consumers that required a JSON array must read `items`. The QGP Exceptions page is the only in-repo caller and is updated.
- **Migration plan:** None. No schema.
- **Rollback strategy:** Revert merge; redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Named truncation | “inbox page ≤200 — not a global facet total” | Page N of up to 200; “more pages follow” when peeked |
| Silent dump | Impossible (hard 200) | Still impossible. Paging does not raise the cap. |
| Invented EXACT / S4 / Entra | Unchanged | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Default request returns at most 200 items. `page_size` cannot exceed 200.
- [x] AC-02: Fetch peeks one extra row. `truncated`/`has_next` true iff another page exists.
- [x] AC-03: FE Previous disabled on page 1. Next enabled when `has_next`. Honesty names page of up to 200.
- [x] AC-04: Filter changes reset to page 1. `page>1` is in the shareable URL.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit (local): `tests/unit/test_exceptions_inbox_paging.py`
- [x] Unit (local): KnowledgeExceptions + knowledgeBankClient vitest
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open Exceptions — page 1 of up to 200. Next disabled when the page is short.
- [x] CUJ-02: Envelope `has_next` enables Next. Honesty says more pages follow.

## 7) Observability & Ops
- Test ids: `exceptions-pager`, `exceptions-page-prev`, `exceptions-page-next`.
- Rollback: revert. Cap is unchanged if paging is reverted.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (`STACK_MAX=1`; admin-squash authorised).
2. Staging: Exceptions inbox Next/Previous; `/api/v1/health` SHA = tip.
3. Promote PROD; Production **Build and Deploy SUCCESS (not skipped)**; STG=PROD=MAIN SHA.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Inbox fails to render; Next walks off the end into a silent empty that looks like zero proposals; page_size above 200 accepted.
- **Rollback steps:** Revert merge; redeploy prior tip via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `feat/exceptions-paging-200`
- Ledger: `scripts/governance/pr_body_exceptions_paging_200.md`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit tests (run locally before PR)
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
