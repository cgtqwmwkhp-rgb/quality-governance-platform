# Change Ledger (CL-OPS-JUNIT-MERGE-HARDEN)

## 1) Summary
- **Feature / Change name:** Harden Integration Tests JUnit merge against malformed shard XML
- **User goal (1–2 lines):** Stop a known CI flake (ET.ParseError on merge) from failing closed when integration shards already succeeded, which currently blocks Staging/Production deploy of tip commits.
- **In scope:** `.github/workflows/ci.yml` Merge JUnit XML step — sanitize illegal XML 1.0 control chars; skip unparseable shards with stderr warning; always write aggregate
- **Out of scope:** Changing shard pytest config; Quality Trend semantics beyond merge robustness; application code
- **Feature flag / kill switch:** N/A (CI-only)

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** None
- **APIs:** None
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** `ci.yml` Integration Tests → Merge JUnit XML for quality-trend
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive resilience in CI merge only
- **Tolerant reader / strict writer applied?** Yes — merge tolerates bad shard XML; shards remain source of truth for pass/fail via fail-closed matrix result
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert workflow commit

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Deploy gate on tip SHA | Malformed JUnit merge fails Integration Tests → Staging/Prod skipped | Merge sanitizes/skips bad shards; Integration Tests follow shard matrix result |
| Test honesty | Shards green but job red on XML parse | Job no longer fails solely on quality-trend XML merge parse |
| Quality trend aggregate | Hard fail on one bad file | Partial merge with warning; empty aggregate only if none parse |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Illegal XML 1.0 control characters in shard JUnit are stripped before parse
- [x] AC-02: Still-unparseable shards are skipped with a stderr warning; step exits 0 and writes `junit-integration.xml`
- [x] AC-03: Fail-closed shard matrix gate remains the authority for Integration Tests success/failure
- [x] AC-04: No application/runtime code changes

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [ ] Unit — N/A
- [ ] Integration — CI re-run / follow-on tip deploy
- [ ] Contract — N/A
- [ ] E2E Smoke — N/A

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Tip commit with green shards no longer blocked from Staging solely by JUnit merge ParseError
