# AGENTS.md

## Cursor Cloud specific instructions

This section captures durable, non-obvious setup/run notes for the Quality Governance
Platform (QGP). Standard commands live in `Makefile`, `CONTRIBUTING.md`, and
`.github/workflows/ci.yml`; this section only records the gotchas that are easy to miss.

### Services / topology
- Backend: FastAPI (Python 3.12 venv), `uvicorn src.main:app --reload --port 8000`.
  Health: `GET /healthz`, `/readyz`; API docs at `/docs`.
- Frontend: React + Vite dev server on port **5173** (`cd frontend && npm run dev`).
  It calls the backend directly at `VITE_API_URL` (`http://localhost:8000`).
- Database: local **PostgreSQL 16** (`quality_governance`, user `postgres` / password `postgres`).
- Redis/Celery are **optional in development** (features degrade gracefully); not needed to run or test the core app.

### Environment already provisioned in the VM snapshot (persist across sessions)
- Python venv at `.venv` (Python 3.12). Use `.venv/bin/...` or activate it.
- `frontend/node_modules` (installed with Node 20).
- Node 20 installed via nvm (`nvm use 20`). See runtime caveat below.
- `.env` (repo root) and `frontend/.env.local` are created and git-ignored; they persist in the snapshot.
- Postgres data directory (migrations already applied, CI/test users seeded).

### Start services each session (update script does NOT start services)
- Start Postgres: `sudo pg_ctlcluster 16 main start` (it is not auto-started on boot).
- Then run the backend and frontend dev servers (`make dev` / `cd frontend && npm run dev`).

### Frontend runtime needs Node 20 (PATH gotcha)
- The repo pins Node 20 (`.nvmrc`, CI). `/exec-daemon/node` (Node 22) is first on `PATH`
  and shadows nvm. Before running the Vite dev server, select Node 20 and prepend it:
  `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 20; export PATH="$NVM_DIR/versions/node/v20.20.2/bin:$PATH"`.
- `esbuild` is pinned to `^0.25.0` in `frontend/package.json` `overrides` (was `>=0.25.0`, which
  npm resolved to 0.28.0 and broke Vite 6's dep optimizer with "Transforming destructuring …
  not supported yet"). If `npm run dev` shows that error, verify `frontend/node_modules/.bin/esbuild --version` is 0.25.x.

### `.env` gotchas (do NOT blindly `cp .env.example .env`)
- The backend `Settings` model (pydantic-settings) forbids extra keys. `.env.example` contains
  frontend-only `VITE_*` keys, SMTP/contact/VAPID keys (consumed via `os.getenv`, not the model),
  and an empty `OTEL_TRACE_SAMPLE_RATE`. Copying it verbatim makes the backend fail to start
  (`extra_forbidden` / float-parse errors). Those keys are commented out in the working `.env`.
- `CORS_ORIGINS` in `.env.example` omits the Vite port; the working `.env` includes
  `http://localhost:5173` (required for the SPA to call the API).
- `ALLOW_LOCAL_PASSWORD_LOGIN=true` is set so email/password login works locally
  (log in at `/login` with `admin@plantexpand.com` / `adminpassword123`).

### Running tests (run suites SEPARATELY, matching `.github/workflows/ci.yml`)
- Do NOT run the whole `pytest tests/` at once. Integration tests use an isolated SQLite DB
  (see `tests/integration/conftest.py`, which sets `DATABASE_URL` to a temp SQLite file). Mixing
  them with the Postgres-bound suites in one process cross-contaminates `DATABASE_URL` and causes
  `drop_all` FK errors (hundreds of setup errors). Run each suite on its own:
  - Unit: `.venv/bin/pytest tests/unit/`
  - Integration (auto-SQLite): `.venv/bin/pytest tests/integration/` (slow, ~10+ min)
  - Smoke / E2E / UAT: run with `TESTING=1` and `DATABASE_URL` pointing at Postgres, e.g.
    `TESTING=1 DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quality_governance .venv/bin/pytest tests/smoke/`
- `TESTING=1` disables rate limiting and skips PAMS init (required for the higher suites).
- Seeded auth accounts come from `PYTHONPATH=. .venv/bin/python scripts/seed_ci_locust_users.py`
  (idempotent): `admin@plantexpand.com` / `adminpassword123` (superuser) and
  `testuser@plantexpand.com` / `testpassword123`.
- Frontend tests: `cd frontend && npx vitest run`.
- Two tests are sensitive to the presence of dev env files and fail only because those files exist
  (not real breakage): backend `tests/unit/test_config_settings.py::TestDefaults::test_debug_defaults_false`
  (because `.env` sets `DEBUG=true`) and frontend `src/config/apiBase.test.ts` (because
  `.env.local` sets `VITE_ENVIRONMENT=development`). CI runs without those files.

### Lint / build
- Backend lint: `make lint` (black, isort, flake8). Frontend lint: `cd frontend && npx eslint src/ --max-warnings 0`.
- Frontend production build: `cd frontend && npm run build` (needs Node 20).
