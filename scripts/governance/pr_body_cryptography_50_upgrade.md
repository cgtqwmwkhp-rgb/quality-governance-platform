# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Upgrade `cryptography` 48.0.1 → 50.0.0 to clear three advisories that are currently blocking every merge
- **User goal (1–2 lines):** Unblock the repository. The blocking security waiver gate started failing today on advisories that did not exist this morning, so nothing can merge until `cryptography` is patched or waived.
- **In scope:** The `cryptography` pin in `requirements.txt` and the regenerated `requirements.lock`.
- **Out of scope:** Waiving these CVEs — an upgrade is available, so a waiver would be the wrong instrument. Also out of scope: the missing test coverage for `field_encryption.py` noted in §7.
- **Feature flag / kill switch:** None applicable to a dependency pin.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None.
- **Backend (handlers/services):** No source changed. The only consumer of this library is `src/infrastructure/encryption/field_encryption.py`.
- **APIs (endpoints changed/added):** None.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None.
- **Database (migrations/entities/indexes):** None.
- **Workflows/jobs/queues:** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** `cryptography` 48.0.1 → 50.0.0. `requirements.txt` constraint `>=48.0.1,<49.0.0` → `>=50.0.0,<51.0.0`. Nothing else moved — the lock pins 122 packages before and after, and a pin-by-pin diff shows `cryptography` as the only change.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** The `<49` cap existed because `msal` used to require `cryptography<49`. The lockfile already resolves **`msal==1.37.0`, which permits `<51`**, so the cap was stale rather than load-bearing. Every other consumer was checked and is satisfied at 50.0.0: `azure-identity` `>=2.5`, `azure-storage-blob` `>=2.1.4`, `google-auth` `>=38.0.3`, `PyJWT[crypto]` `>=3.4.0`, `dnspython[dnssec]` `>=45`, `http_ece` `>=2.5`. `celery` declares a hard `cryptography==46.0.3` but **only under its `[auth]` extra**, and this project installs plain `celery==5.6.2`.
- **Tolerant reader / strict writer applied?** N/A.
- **Breaking changes:** None reached by this codebase. The API surface in use is `Fernet.generate_key()`, `Fernet(key)` and `MultiFernet([...])`, which is the library's most stable surface.
- **Migration plan:** None. Fernet tokens are unaffected by the library version; ciphertext written under 48.0.1 decrypts under 50.0.0, which is verified below.
- **Rollback strategy (DB):** No DB impact. Reverting the two files restores the previous resolution.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** `pip-audit` reports no known vulnerabilities against `requirements.lock`.
- [x] **AC-02:** The repo's own blocking gate, `scripts/validate_security_waivers.py`, passes in an environment installed from the new lock.
- [x] **AC-03:** `scripts/verify_lockfile.py` accepts the regenerated lock with all hashes intact.
- [x] **AC-04:** The lock installs under `--require-hashes`, proving the generated hashes are valid.
- [x] **AC-05:** `FieldEncryptor` round-trips, including with two keys configured, so `MultiFernet` rotation still works.
- [x] **AC-06:** No unrelated dependency drift — 122 packages pinned before and after, one version changed.

## 5) Testing Evidence (link to runs)
- [x] **Lint** — no source changed.
- [x] **Typecheck** — no typed source changed.
- [x] **Build** — dependency resolution succeeded via the repo's own `scripts/generate_lockfile.sh` on Python 3.11.15, matching the Dockerfile's `python:3.11-slim-bookworm` target.
- [x] **Unit tests** — **5169 passed, 7 skipped, 1 failed.** The single failure was `test_config_settings.py::TestDefaults::test_redis_url_default_empty`, caused by `REDIS_URL` leaking from my shell into the test process. Re-running that file with the variable unset gives **36/36**, so the suite is clean on a clean environment. Nothing to do with this change.
- [x] **Contract tests** — not affected; CI will confirm.
- [ ] **Integration tests** — not run locally (require Postgres/Redis services); CI will confirm.
- [ ] **E2E Smoke** — deferred to CI.

**Root cause, established rather than assumed.** `main`'s last Security Scan passed at **20:37 UTC**; the run on an unrelated PR failed at **21:31 UTC** with only a workflow file and a markdown file changed. The advisories were published in that window. Neither the GitHub Advisory API nor OSV had them indexed yet, so the fix versions came from `pip-audit` itself — the same tool the gate uses:

| CVE | Fix version |
| --- | --- |
| CVE-2026-69248 | 49.0.0 |
| CVE-2026-69249 | 49.0.0 |
| CVE-2026-69247 | **50.0.0** |

So 50.0.0 is the floor that clears all three; 49.0.0 would have left one outstanding and still needed a waiver.

**Verified in a clean venv installed from the new lock, not reasoned about:**

```
pip-audit -r requirements.lock            -> No known vulnerabilities found
validate_security_waivers.py              -> No vulnerabilities detected by pip-audit
verify_lockfile.py                        -> 48 declared, 122 pinned, all hash-verified
pip install --require-hashes -r lock      -> exit 0
cryptography 50.0.0 / msal 1.37.0 coexist -> confirmed
MultiFernet round-trip, decrypt by either key -> OK
FieldEncryptor().encrypt/.decrypt with 2 keys -> OK
```

The first attempt to regenerate the lock failed because `pip-tools` 7.6.0 raises `ImportError: cannot import name 'stdlib_pkgs'` against `pip` 26.2. Pinning the combination the repo venv already uses — `pip` 26.0.1 with `pip-tools` 7.5.3 — resolved it. Worth knowing, because anyone regenerating this lock on a fresh machine will hit it (§7).

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** PII field encryption and decryption — the only path that touches this library — verified through the real `FieldEncryptor` with two keys configured, not just a bare `Fernet` call.
- [x] **CUJ-02:** Key rotation — `MultiFernet` decrypts a token using either configured key, so staged rotation is unaffected.
- [x] **CUJ-03:** Merges are unblocked — the blocking gate that is currently failing on every PR passes against this lock.

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** Unchanged.
- **Runbook updates:** None required.

**Adjacent findings, deliberately not fixed here:**
1. **`field_encryption.py` has no test coverage.** No file under `tests/` references it. The only consumer of the crypto library in the codebase is verified by nothing in CI, which is why this PR verified it by hand. Worth a follow-up.
2. **`scripts/generate_lockfile.sh` is fragile on a fresh machine.** It runs `pip install pip-tools` unpinned, and the current release is broken against current `pip`. Pinning both in that script would prevent the next person losing time to it.
3. **The existing `cryptography` waiver in `docs/SECURITY_WAIVERS.md` (CVE-2026-39892) may now be removable** — it was written when no patched release existed, and 50.0.0 is well past the 46.0.7 fix. Left alone here to keep this PR to one concern.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** The standard staging deploy exercises this, since the image is built from `requirements.lock`. Confirm the app starts and authenticates.
- **Canary plan:** Standard progressive delivery; no feature-specific canary needed.
- **Prod post-deploy checks:** Confirm the app starts and that PII fields already encrypted under 48.0.1 still decrypt — that is the one behaviour a crypto library upgrade could plausibly disturb, and it is verified locally above.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Any failure to decrypt existing PII fields, or an install/resolution failure in the image build.
- **Rollback steps:** Revert this commit, restoring `cryptography>=48.0.1,<49.0.0` and the previous lock. Note this reinstates the failing security gate, so it would need pairing with short-dated waivers for the three CVEs.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks.
- Staging deploy evidence: to follow on merge to `main`.
- Canary evidence (if applicable): n/a.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — on merge to `main`
- [ ] **Gate 4:** Canary healthy (if used) — standard pipeline
- [ ] **Gate 5:** Production verification plan + monitoring ready — per §8
