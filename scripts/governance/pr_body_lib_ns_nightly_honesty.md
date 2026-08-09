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

## 7–10) Ops / Release / Rollback / Evidence

- Release: merge after W8 LIVE preferred (parallel prep OK); tip-chase; do not claim W9 DONE at merge
- Rollback: revert merge
- Evidence: master plan W9; baseline JSON; unit pins

---

# Gate Checklist

- [x] Gate 0–1 scope + ledger
- [ ] Gate 2 CI
- [ ] Gate 3–5 tip LIVE (after merge — not now)
