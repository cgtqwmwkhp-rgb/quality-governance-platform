# Contributing to Quality Governance Platform

## Development Setup

See [docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md) for setting up your local environment.

## Code Style

- **Python**: We use `black` (line length 120), `isort` (profile: black), and `flake8`
- **TypeScript**: Strict mode enabled, no `any` types allowed
- **Type checking**: `mypy` with strict settings

Run formatting before committing:
```bash
black src/ tests/ --line-length 120
isort src/ tests/ --profile black
flake8 src/ tests/
mypy src/
```

## Branch Naming

- `feature/` - New features (e.g., `feature/capa-module`)
- `fix/` - Bug fixes (e.g., `fix/tenant-isolation`)
- `refactor/` - Code refactoring
- `docs/` - Documentation updates
- `chore/` - Maintenance tasks

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests for new functionality (minimum 80% coverage)
3. Ensure CI passes (all quality gates green)
4. Request review from at least one team member
5. Squash merge after approval

## Commit Messages

Use conventional commit format:
```
type(scope): brief description

Optional longer description explaining the change.
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `perf`

## Testing Requirements

- All new code must have corresponding tests
- Unit test coverage: minimum 85%
- Integration test coverage: minimum 70%
- Overall coverage must not drop below 80%

## Code Review Checklist

- [ ] Code follows project style guidelines
- [ ] Tests pass locally
- [ ] No `any` types in TypeScript
- [ ] API endpoints have authentication
- [ ] Database queries use proper indexes
- [ ] Sensitive data is not logged
