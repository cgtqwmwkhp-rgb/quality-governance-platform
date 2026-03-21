# Build reproducibility and environment parity

This document describes how we keep **deterministic builds**, how to **verify** reproducibility, how **dev / staging / production** differ, and how **CI and deploy workflows** guard against drift—including Docker layering and **artifact digest** verification.

---

## Deterministic builds

### Docker base images (pinned by digest)

The root **`Dockerfile`** uses the same **Python 3.11 slim bookworm** image for both builder and production stages, pinned with an **`@sha256:...` digest** (not only a floating tag). That pins the filesystem baseline independent of tag movement on the registry.

### Python dependencies (`requirements.lock` + hashes)

- **`requirements.lock`** is generated with **hashes** (`pip-compile ... --generate-hashes`).
- CI **Lockfile Freshness Check** compares a fresh compile to the committed lockfile and fails on package version drift.
- The Docker **builder** stage runs `pip install -r requirements.lock` when the file is present, so image builds resolve the same dependency graph as CI.

### Frontend installs (`npm ci`)

- The **Frontend Tests** and **Performance Budget** jobs run **`npm ci`** in `frontend/`, which installs exactly from **`package-lock.json`** (no semver drift during CI).
- A follow-up step verifies that all `package.json` dependencies appear in the lockfile.

Together, pinned base images + hashed Python locks + `npm ci` minimize “works on my machine” variance.

---

## Reproducibility proof

To show that two builds are equivalent enough for audit:

1. **Same inputs** — Check out the **same git commit** on two machines or twice locally (`git rev-parse HEAD`).
2. **Docker** — Build with `docker build` from a clean context; record the resulting image **digest** (`docker inspect` or registry manifest).
3. **Compare** — For the **same Dockerfile and lockfiles**, builder stages should produce the same installed package set; any digest difference usually means different cache usage, different platform, or upstream lock/hash drift—re-run after `docker builder prune` if investigating.
4. **CI parity** — Compare CI’s image digest (after push to ACR) to a local build only when using the **same build-args and lockfiles**; registry digest is the deployment source of truth.

For application **artifacts** (bundles, wheels), compare checksums of built outputs when the build pipeline is fully pinned.

---

## Environment parity matrix

| Dimension | Local dev | Staging | Production |
|-----------|-----------|---------|------------|
| **App entry** | `uvicorn` / IDE | Azure App Service (container from ACR) | Azure App Service (container from ACR) |
| **`APP_ENV`** | `development` / `.env` | `staging` (set in deploy workflow) | `production` (set in deploy workflow) |
| **Secrets** | `.env`, local secrets | Azure Key Vault → app settings | Azure Key Vault → app settings |
| **Database** | Local / docker Postgres | Managed Postgres URL from KV | Managed Postgres URL from KV |
| **CORS** | Often permissive locally | Tied to App Service host | Tight allowlist |
| **Migrations** | `alembic upgrade` manually | ACI/job in deploy workflow | ACI/job in deploy workflow |
| **Observability** | Optional / debug | Azure Monitor wiring | Azure Monitor wiring |

Production enforces **stricter config validation** (fail-fast for unsafe secrets); see ADR-0002 and `tests/test_config_failfast.py`.

---

## Configuration drift detection

### `config-drift-guard` (CI)

Job **Configuration Drift Guard** in `.github/workflows/ci.yml` scans a fixed list of files for a **forbidden legacy string** (historical ACA environment id). If found, the job fails with guidance to use current **azure-app-service** staging URLs and naming.

**Files checked (as of workflow definition):**

- `scripts/etl/config.py`
- `docs/evidence/environment_endpoints.json`
- `.github/workflows/deploy-staging.yml`
- `scripts/infra/provision-aca-staging.sh`

Extend this list when new canonical env docs or scripts are added.

---

## Docker build process

- **Multi-stage build** — **Builder** venv contains compiled dependencies; **production** copies `/opt/venv` and application code only, reducing attack surface.
- **Pinned base images** — Digest-pinned `python:3.11-slim-bookworm` for reproducibility.
- **Layer caching** — Dependency layers run before `COPY src/` so code edits reuse cached installs when rebuilding locally or in CI agents with cache.
- **Non-root user** — Production stage runs as `appuser`.
- **Health check** — `curl` against `/healthz` inside the container.

Deploy pipelines build with `docker build` and push tags including **`${{ github.sha }}`** for traceability.

---

## Artifact verification (deploy workflows)

**Staging deploy** (`.github/workflows/deploy-staging.yml`):

1. Build and push image tagged with the **commit SHA** and `latest`.
2. **Capture expected image digest** from ACR (`az acr repository show-manifests`) and require **exactly one** manifest for the SHA tag.
3. Validate digest format (`sha256:...`).
4. Deploy to Azure Web App using **`images: ${{ env.IMAGE_DIGEST_REF }}`** — i.e. **`repository@sha256:...`**, not only a mutable tag.

The same pattern ensures what runs in App Service matches the **immutable digest** resolved at deploy time. **Production** workflow should follow the same digest-first deployment discipline (see `.github/workflows/deploy-production.yml`).

Build metadata such as **`BUILD_SHA`** and **`BUILD_TIME`** is set in app settings for runtime verification and support.

---

## References

- `Dockerfile` — multi-stage, digests, `requirements.lock`
- CI: `.github/workflows/ci.yml` — lockfile check, frontend `npm ci`, `config-drift-guard`
- Deploy: `.github/workflows/deploy-staging.yml` — digest capture and `IMAGE_DIGEST_REF`
- Module boundaries: `docs/architecture/module-boundaries.md`
