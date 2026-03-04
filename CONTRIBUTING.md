# Contributing to QGP

> **Canonical repository:** [`cgtqwmwkhp-rgb/quality-governance-platform`](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform)
> All development, issues, and pull requests should target this repository.
> The former `Plantexpand/quality-governance-platform` mirror is retired as of March 2026.

## Prerequisites

| Tool       | Version | Check              |
|------------|---------|--------------------|
| Python     | 3.11+   | `python --version` |
| Node.js    | 20+     | `node --version`   |
| npm        | 10+     | `npm --version`    |
| Docker     | Latest  | `docker --version` |
| PostgreSQL | 15+     | Local or via Docker |

## Getting Started

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd qgp

# 2. Create and activate a Python virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install all dependencies
make install

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your local database URL, Azure AD credentials, etc.

# 5. Run database migrations
make migrate

# 6. Start the backend
make dev

# 7. Start the frontend (separate terminal)
make dev-frontend
```

The backend runs at `http://localhost:8000` and the frontend at `http://localhost:5173`.

## Branch Naming

All branches must use a prefix:

| Prefix   | Purpose                          |
|----------|----------------------------------|
| `feat/`  | New features                     |
| `fix/`   | Bug fixes                        |
| `chore/` | Dependencies, CI, tooling        |
| `docs/`  | Documentation-only changes       |

Examples: `feat/incident-export`, `fix/complaint-status-filter`, `chore/upgrade-fastapi`.

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]
```

**Types:** `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `ci`

**Scopes:** `incidents`, `complaints`, `risks`, `audits`, `capa`, `frontend`, `auth`, `infra`, `api`

Examples:
```
feat(incidents): add CSV export for incident list
fix(auth): handle expired refresh tokens gracefully
chore(ci): add coverage threshold to test pipeline
```

## Pull Request Process

1. **Create your branch** from `main` using the naming convention above.
2. **Write a clear PR description** covering:
   - What changed and why
   - How to test it
   - Screenshots for UI changes
3. **All CI checks must pass** before review — linting, tests, build.
4. **At least one approval** is required to merge.
5. **Squash merge** into `main`. The PR title becomes the commit message, so make it descriptive.

## Code Style

### Python (backend)

- **Formatter:** [Black](https://black.readthedocs.io/) (line length 88)
- **Import sorting:** [isort](https://pycqa.github.io/isort/) (configured in `pyproject.toml`)
- **Linter:** [Flake8](https://flake8.pycqa.org/)
- Run `make lint-fix` to auto-format before committing.

### TypeScript / React (frontend)

- **Linter:** [ESLint](https://eslint.org/) with strict React + a11y rules
- **Formatter:** [Prettier](https://prettier.io/) (via editor integration)
- Run `cd frontend && npx eslint src/ --max-warnings 0` to check.

## Testing

- **New features must include tests.** PRs adding functionality without tests will be sent back.
- Backend tests live in `tests/unit/` and `tests/integration/`.
- Frontend tests use Vitest; place them next to the component as `*.test.tsx`.
- Run `make test` (backend) or `make test-frontend` (frontend) locally before pushing.

## Documentation

- Update `ARCHITECTURE.md` if you change system structure, add modules, or modify data flow.
- Add docstrings to new API endpoints, services, and non-trivial functions.
- Update the README if setup steps change.

## Questions?

Open a GitHub Discussion or reach out in the project's Teams channel.
