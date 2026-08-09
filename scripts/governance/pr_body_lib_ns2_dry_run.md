# Change Ledger (CL-LIB-NS2-DRY-RUN)

## Change Ledger

| Field | Value |
|---|---|
| Wave | Northern Star **W5b / NS-2** dry-run ingest |
| Branch | `feat/lib-ns2-dry-run-ingest` |
| Base | `origin/main` @ `f872eb1a` (W4 LIVE) |
| Migration | None — scripts + pack hygiene only |
| Risk | Low — no runtime write path |
| Reversible | Yes |
| ADR | ADR-0023 § Amendment — ingest model |
| Deferred | Silent bulk import (forbidden); steward reissue of PEL-IT-2005; W6 WF |

## 1) Summary

Scripts-only dry-run against the Northern Star pack (388 documents):

- `python -m scripts.governance.library.northern_star_dry_run_ingest`
- Reports R01–R03 / R26 / R32, Supersedes self-loops, second parents
- **Never writes** to the database
- Removes 6 Supersedes self-loops from `northern-star-v6.json` (pack hygiene)
- Leaves `PEL-IT-2005` (band 2 vs level 5) as a Critical report finding — R29 forbids silent renumber; steward reissue later

## 2) Impact Map

| Area | Change |
|---|---|
| `scripts/governance/library/northern_star_dry_run_ingest.py` | New dry-run reporter |
| `specs/governance-library/northern-star-v6.json` | Drop 6 self-loop edges + finding note |
| `specs/governance-library/README.md` | W5b usage pointer |
| `tests/unit/test_northern_star_dry_run_ingest.py` | Fixture + live-pack pins |

## 3) Compatibility & Data Safety

- No alembic, no OpenAPI, no app write path
- Self-loop removal only deletes invalid `from==to` Supersedes rows

## Compliance Delta

| Control | Before | After |
| --- | --- | --- |
| Ingest honesty | Pack findings only | Executable dry-run exit≠0 on Critical |
| Self-loops | 6 Supersedes self-edges | Removed |
| PEL-IT-2005 R02 | Known tip-map note | Surfaced every dry-run as Critical |

## 4) Acceptance Criteria

- [x] AC-01: Dry-run reports 388 documents
- [x] AC-02: No Supersedes self-loops remain in pack
- [x] AC-03: Multi-parent count matches tip-map (14)
- [x] AC-04: PEL-IT-2005 R02 remains Critical (no silent renumber)
- [x] AC-05: Script never opens a DB session

## 5) Testing Evidence

- [x] Unit tests for fixture + live pack
- [ ] Full CI on PR
- [ ] Tip-chase after merge (docs/scripts deploy with tip)

## 6) Critical Journeys

- [x] CUJ-01: Run dry-run → text report + exit 1 while PEL-IT-2005 unresolved
- [x] CUJ-02: `--json` emits structured findings

## 7–10) Ops / Release / Rollback / Evidence

- Release: merge → tip-chase; next wave W6 WF
- Rollback: revert merge
- Evidence: master plan W5b; pack findings L2-W5b-01

---

# Gate Checklist

- [x] Gate 0–1
- [ ] Gate 2 CI
- [ ] Gate 3–5 tip LIVE
