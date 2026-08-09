# Change Ledger (CL-LIB-NS-NIGHTLY-HONESTY)

## Change Ledger

| Field | Value |
|---|---|
| Wave | Northern Star **W9 / NS-NIGHTLY** R08/R25/R30 honesty |
| Branch | `feat/lib-ns-nightly-honesty-reports` |
| Base | `origin/main` @ `8ab173ce` (W7 LIVE) |
| Migration | None — scripts + baseline + scheduled workflow only |
| Risk | Low — no runtime write path; no W8 route overlap |
| Reversible | Yes |
| ADR | ADR-0023 § Amendment — staged hardness (nightly warn/alert) |
| Deferred | DB-backed overdue fan-out; owner email alerts; silent legacy remaps (forbidden) |

## 1) Summary

Smallest honest W9 slice — pack-based nightly honesty for R08 / R25 / R30:

- `python -m scripts.governance.library.northern_star_nightly_honesty`
- `--guard` delivery gate vs `docs/governance/library_ns_nightly_honesty_baseline.json`
- Scheduled + PR-path workflow `.github/workflows/ns-nightly-honesty.yml`
- **Never writes** to the database
- Parallel-safe vs W8 (no `document_graph` / Structure map / Parent PEL export files)

Live pack pins (honesty, not greenwash):

| Rule | Measured |
|---|---|
| R08 L2 Policy without L3+ child | **30** |
| R25 Issued missing `review_date` | **8** (pack has **0** review dates; overdue uncomputed) |
| R30 controlled coverage gaps (`legacy_ref` missing) | **220** (master plan planning estimate ~135 — report the real number) |

## 2) Impact Map

| Area | Change |
|---|---|
| `scripts/governance/library/northern_star_nightly_honesty.py` | New honesty reporter + delivery guard |
| `docs/governance/library_ns_nightly_honesty_baseline.json` | Honesty floors (refuse fabricated zeros) |
| `.github/workflows/ns-nightly-honesty.yml` | Schedule + PR path + artifact |
| `tests/unit/test_northern_star_nightly_honesty.py` | Fixture + live-pack pins |
| `specs/governance-library/README.md` | W9 usage pointer |
| `scripts/governance/pr_body_lib_ns_nightly_honesty.md` | This Change Ledger |

## 3) Compatibility & Data Safety

- No alembic, no OpenAPI, no app write path
- Does not touch W8 surfaces (`document_graph*`, Structure map, register Parent PEL)

## Compliance Delta

| Control | Before | After |
| --- | --- | --- |
| R08/R25/R30 nightly | No Library nightly honesty job | Executable pack report + scheduled workflow |
| Silent green | Possible to claim zero gaps | `--guard` fails below honesty floors |
| R30 legacy debt | Planning estimate ~135 | Measured **220** coverage gaps reported honestly |
| R25 overdue | Easy to invent `0` overdue | Explicitly uncomputed while `review_date` absent |

## 4) Acceptance Criteria

- [x] AC-01: Script reports R08 / R25 / R30 counters from northern-star pack
- [x] AC-02: Script never opens a DB session / never writes
- [x] AC-03: Delivery guard fails on fabricated zero gaps
- [x] AC-04: Live pack pins R08=30, R30 coverage ≥135 (measured 220), R25 review_date absent honesty
- [x] AC-05: No W8 path files in this PR
- [x] AC-06: Change Ledger body present for `pnpm validate:pr-body` / gate checklist

## 5) Testing Evidence

- [x] Unit tests fixture + live pack + guard
- [ ] Full CI on PR
- [ ] Scheduled workflow first manual dispatch after merge
- [ ] Tip-chase after merge (scripts deploy with tip) — **not this PR's merge**

## 6) Critical Journeys

- [x] CUJ-01: Run report → text/JSON with R08/R25/R30 findings
- [x] CUJ-02: `--guard` exits 0 on current pack; exits 1 if counters zeroed
- [x] CUJ-03: Workflow uploads honesty artifact

## 7) Observability & Ops

- Report-only job: stdout + uploaded artifact `ns-nightly-honesty-report` (JSON + text).
- No new runtime metrics, AuditLog events, or owner email alerts (deferred).
- Delivery guard (`--guard`) fails the workflow when honesty floors are breached (fabricated zeros).
- Schedule: cron `15 3 * * *` UTC + `workflow_dispatch` + PR path on honesty files.

## 8) Release Plan

1. Hold merge until W8 (#1684) is LIVE unless explicitly told otherwise — this PR is parallel prep only.
2. Merge this PR to `main` after W8 LIVE; `CI - Default` green on the tip SHA.
3. Tip-chase is owned by the governed tip path after merge — **do not tip-chase from this babysit**.
4. First scheduled / manual `ns-nightly-honesty` dispatch after merge uploads the honesty artifact.
5. Do **not** claim W9 DONE at merge — DONE = tip LIVE + honesty job verified.

## 9) Rollback Plan (Mandatory)

- **Trigger:** Nightly honesty job red on real pack drift, guard false-positive blocking unrelated PRs, or workflow flake after install.
- **Rollback steps:**
  1. Disable/skip the scheduled workflow (or revert the merge commit) — no DB or app image dependency for pack-only honesty.
  2. If a baseline floor is wrong after an intentional pack improvement, update `docs/governance/library_ns_nightly_honesty_baseline.json` via a follow-up PR (never weaken by inventing zeros).
  3. No schema to unwind; no feature flag.
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack

- Authority: Northern Star master plan wave W9 / NS-NIGHTLY (R08 / R25 / R30).
- ADR: ADR-0023 § Amendment — staged hardness (nightly warn/alert).
- Baseline: `docs/governance/library_ns_nightly_honesty_baseline.json`.
- Script: `scripts/governance/library/northern_star_nightly_honesty.py`.
- Workflow: `.github/workflows/ns-nightly-honesty.yml`.
- Ledger file: `scripts/governance/pr_body_lib_ns_nightly_honesty.md`.
- Live pack pins: R08=30, R25 issued missing review_date=8 (overdue uncomputed), R30 coverage gaps=220.

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger; pack-only honesty; no W8 path overlap
- [x] **Gate 1:** No DB writes / no silent greenwash — delivery guard floors held
- [ ] **Gate 2:** CI green on the PR
- [x] **Gate 3:** Behaviour verified locally — report + `--guard` OK on live pack; unit pins
- [x] **Gate 4:** No migration, no data change, no tip-chase from this PR
- [ ] **Gate 5:** DONE = tip LIVE after merge + first honesty artifact — not claimed here (hold merge until W8 LIVE)
