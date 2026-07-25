# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Controlled redis-py 8.x major (staging-bake required)
- **User goal (1-2 lines):** Move the Redis client to the maintained 8.x line used for cache, rate-limit, idempotency, and health checks — without bulk-merging Dependabot.
- **In scope:** `requirements.txt` → `redis>=8.0.1,<9.0.0`; lock pin `redis==8.0.1`; unit guards for constraint/lock/async call sites. Supersedes Dependabot #874.
- **Out of scope:** Redis **server** version upgrade, Celery major, frontend majors, google-genai (separate PR).
- **Feature flag / kill switch:** App already degrades when Redis unavailable on several paths; monitor `/health` Redis check after deploy.

## 2) Impact Map (what changed)
- **Frontend:** None.
- **Backend:** No application code changes — client library major only.
- **APIs / Schemas / Database:** None.
- **Workflows:** None.
- **Dependencies:** `requirements.txt`, `requirements.lock` (`redis` 7.4.1 → 8.0.1 only).

## 3) Compatibility & Data Safety
- **Compatibility strategy:** redis-py 8 keeps the asyncio APIs we use (`from_url`, `ping`, `setex`, `scan_iter`, `pipeline`, `aclose`). Broker URL format unchanged for Celery/kombu.
- **Breaking changes:** Environments that pin old redis-py via unlocked install must use the lock.
- **Migration plan:** CI green → **staging bake** (cache hit/miss, login lockout, rate limit, Celery broker ping) → prod.
- **Rollback strategy:** Redeploy prior SHA / restore redis`<8` constraint + prior lock pin.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Constraint is redis 8.x (`>=8.0.1,<9.0.0`).
- [x] AC-02: Lock pins `redis==8.0.1` with minimal unrelated churn.
- [x] AC-03: Known call sites still use `redis.asyncio`.
- [x] AC-04: Supersedes Dependabot #874; **do not merge until staging bake evidence is linked**.

## 5) Testing Evidence (link to runs)
- [x] Unit tests — `tests/unit/test_redis_major_floor.py` (local pass).
- [ ] Full CI — this PR checks tab.
- [ ] Staging bake — required before Gate 3: `/health` Redis OK, Celery worker consume, cache set/get, rate-limit path.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Lock/constraint declare redis-py 8.x.
- [ ] CUJ-02: Staging health + cache + Celery broker remain healthy after bake (pending staging).

## 7) Observability & Ops
- **Logs:** Watch Redis connection errors in API/Celery after deploy.
- **Metrics:** Health Redis check; cache error rate; Celery queue lag.
- **Alerts:** Existing health/Celery monitors.
- **Runbook updates:** Note redis-py client major ≠ Redis server major.

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification (mandatory):** Deploy this SHA to staging; verify health Redis section, submit an idempotent write, confirm Celery task execution, exercise login lockout/rate-limit lightly.
- **Canary plan:** Normal governed promotion after staging evidence.
- **Prod post-deploy checks:** `/health` 200 + Redis check OK; Celery lag stable 15m.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Redis client exceptions, Celery broker disconnects, or elevated 5xx after deploy.
- **Rollback steps:** Redeploy previous application SHA (prior lock pin).
- **Owner:** Platform team.

## 10) Evidence Pack (links)
- CI run(s): This PR checks tab.
- Staging deploy evidence: **Required before merge**.
- Canary evidence (if applicable): After promotion.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked) — **BLOCKING for this PR**
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
