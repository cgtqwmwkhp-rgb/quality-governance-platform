# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Bump `ip-address` 10.2.0 → 10.4.0 (frontend, dev-only transitive)
- **User goal (1–2 lines):** Clears the only **high**-severity Dependabot advisory open on `main`, plus two mediums against the same package. Authored by Dependabot; this ledger was added by hand so the PR can pass the Change Ledger gate.
- **In scope:** Three lines in `frontend/package-lock.json` — the `version`, `resolved` and `integrity` fields of the single `node_modules/ip-address` entry.
- **Out of scope:** The four remaining advisories. `react-router` needs a 6→8 major bump (#1307) and real testing; `react-router-dom` has no published fix; `uuid` has **no open PR at all** and nothing is currently coming to fix it.
- **Feature flag / kill switch:** None applicable.

## 2) Impact Map (what changed)
- **Frontend:** No source change. Lockfile only; no `package.json` edit, so the declared dependency range is untouched.
- **Backend / APIs / Schemas / Database / Workflows / Config:** None.
- **Dependencies:** One transitive dev dependency moves by two minor versions.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Patch/minor lockfile bump within the existing `^10.0.1` range already declared by `socks`. No resolution changes elsewhere in the tree — the diff is exactly three lines.
- **Breaking changes:** None.
- **Migration plan / Rollback strategy (DB):** No data impact.

**Honest severity assessment — the "high" rating overstates the risk to us.** The advisory (Address4 decoding leading-zero octets as decimal) is scored against the library's worst case, which is code performing IP allowlisting or SSRF filtering on untrusted input. That is not what this package does here. Traced through the lockfile, `ip-address` enters the tree by exactly one path, and every hop is `dev: true`:

```
<root> devDependencies
  └─ @lhci/cli  (also: @puppeteer/browsers)
       └─ proxy-agent
            └─ pac-proxy-agent / socks-proxy-agent
                 └─ socks
                      └─ ip-address
```

It is Lighthouse CI and Puppeteer proxy handling — build and test tooling that never reaches the production bundle. There is one `ip-address` entry in the lockfile and it is marked `"dev": true`.

So this is not urgent remediation. It is a three-line, zero-production-surface change that happens to clear the only high-severity alert on the repository, which makes the risk of taking it lower than the risk of leaving the alert open and continuing to triage around it.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** `ip-address` resolves to ≥ 10.3.1, the first patched version for the high-severity advisory.
- [x] **AC-02:** All three open `ip-address` advisories (1 high, 2 medium) are closed by this version.
- [x] **AC-03:** The change is confined to the lockfile and introduces no production dependency.
- [x] **AC-04:** The frontend still builds and its tests pass.
- [x] **AC-05:** Lockfile integrity and install reproducibility hold.
- [x] **AC-06:** Checks are re-run against current `main` rather than relied on from an older base.

## 5) Testing Evidence (link to runs)
- [x] **Lint / Typecheck / Build / Unit / Contract / E2E** — CI on this PR: **51 checks passing**, including `Frontend Tests`, `Build Check`, `Storybook Build`, `Performance Budget (PR-04)`, `End-to-End Tests`, `Dependency Install Integrity`, `Lockfile Validity Check` and `Dependency Vulnerability Check`.

**AC-01 / AC-02 — fix versions checked against the live alert data**, not inferred from the version number:

| Severity | First patched version | 10.4.0 satisfies |
|---|---|---|
| high | 10.3.1 | yes |
| medium | 10.2.1 | yes |
| medium | 10.2.2 | yes |

**AC-03 — dependency chain traced from the lockfile**, reproduced in §3. One entry, `dev: true`, reachable only from `@lhci/cli` and `@puppeteer/browsers`.

**AC-06 — the branch was 8 commits behind `main`** (base `13883358`, tip `ac3e9e13`) with its checks dated 2026-08-03T22:24, i.e. predating the `cryptography` CVE fix that unblocked merges. `git merge-tree` showed zero conflict markers, but stale green is not green, so the branch was updated to current `main` and the full suite re-run before merge.

**Not verified:** I did not execute Lighthouse or Puppeteer locally against the new resolution. Coverage for that comes from the CI suite above, which exercises the frontend build and E2E path.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** The frontend builds and its unit and E2E suites pass with the new resolution — the only way a dev-tooling dependency can break anything here.
- [x] **CUJ-02:** No production runtime journey is touched, because the package is dev-only and absent from the shipped bundle.
- [x] **CUJ-03:** A clean install remains reproducible — `Dependency Install Integrity` and `Lockfile Validity Check` both pass with the new integrity hash.

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** Unchanged.
- **Runbook updates:** None.

**Adjacent finding, not fixed here.** The `Auto-merge Dependabot (patch/minor)` check on this PR fails with:

```
failed to create review: GraphQL: GitHub Actions is not permitted to approve pull requests. (addPullRequestReview)
```

That is a repository/organisation setting, not a code defect, so the auto-merge workflow **cannot succeed as written** — it will fail on every Dependabot PR. Combined with the Change Ledger gate, which Dependabot cannot satisfy because it does not author ledgers, this is why 28 Dependabot PRs are currently open and none can merge unattended. Raised separately; this PR only unblocks itself.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Standard pipeline. No dev-only dependency reaches the deployed artefact, so there is nothing environment-specific to verify.
- **Canary plan:** Not applicable.
- **Prod post-deploy checks:** Standard health probes. The production container is unaffected by a dev dependency.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Frontend build or Lighthouse CI failing in a way traceable to the new resolution.
- **Rollback steps:** Revert the commit, restoring the three lockfile lines to 10.2.0. No runtime or data impact, and no coordination needed.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks after the branch update.
- Advisory source: repository Dependabot alerts, `frontend/package-lock.json`.
- Dependency chain: derived from `frontend/package-lock.json` `packages` map.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — standard pipeline; no dev dependency in the artefact
- [ ] **Gate 4:** Canary healthy (if used) — n/a
- [ ] **Gate 5:** Production verification plan + monitoring ready — standard health probes
