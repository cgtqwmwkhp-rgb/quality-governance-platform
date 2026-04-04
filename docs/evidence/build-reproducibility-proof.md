# Build Reproducibility Proof (D30)

Evidence that builds are deterministic and reproducible from source.

## Build Chain

```
Source (git SHA) → CI Build → Container Image (digest) → Deployment (slot swap)
```

Every production deployment can be traced back to a specific git commit.

## Determinism Controls

| Control | Mechanism | Evidence |
|---------|-----------|----------|
| Python dependencies pinned | `requirements.lock` (pip-compile) | `lockfile-check` CI job |
| npm dependencies pinned | `package-lock.json` | `npm ci` (not `npm install`) |
| Python version pinned | `python-version: "3.11"` in CI | `.github/workflows/ci.yml` |
| Node version pinned | `node-version: "20"` in CI | `.github/workflows/ci.yml` |
| Docker base image pinned | `python:3.11-slim-bookworm` with SHA digest | `Dockerfile` |
| Build SHA embedded | `VITE_BUILD_SHA` env var | Frontend build step |
| Backend SHA available | `GET /api/v1/meta/version` endpoint | `src/main.py` |

## Lockfile Freshness Verification

The `lockfile-check` CI job (`.github/workflows/ci.yml`) verifies that `requirements.lock` matches a fresh `pip-compile` output. If the lockfile drifts due to upstream package updates, the CI job fails and requires a lockfile regeneration.

```bash
# Regenerate lockfile (uses requirements.txt as input, outputs requirements.lock)
pip-compile requirements.txt -o requirements.lock --generate-hashes --strip-extras
```

## npm Lockfile Verification

The `frontend-tests` CI job uses `npm ci` which:
1. Fails if `package-lock.json` is out of sync with `package.json`
2. Installs exact versions from the lockfile (no resolution)
3. Validates lockfile integrity

## Container Image Traceability

| Artifact | Location | Retention |
|----------|----------|-----------|
| Docker image | Azure Container Registry (Basic) | Tagged releases retained; untagged purged after 30 days |
| Build SHA | Image label + health endpoint | Permanent (as long as image exists) |
| CI build log | GitHub Actions | 90 days |

## Verification Procedure

To verify a production deployment matches source:

1. Get the build SHA from production: `curl https://app-qgp-prod.azurewebsites.net/api/v1/meta/version`
2. Check the frontend build SHA in browser console: `[QGP] Build: <sha> @ <timestamp>`
3. Match both SHAs to the git commit: `git log --oneline <sha>`
4. Verify the lockfiles at that commit match current production dependencies

## Related Documents

- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) — CI pipeline with lockfile checks
- [`requirements.lock`](../../requirements.lock) — Python dependency lockfile
- [`frontend/package-lock.json`](../../frontend/package-lock.json) — npm lockfile
- [`Dockerfile`](../../Dockerfile) — container build definition
