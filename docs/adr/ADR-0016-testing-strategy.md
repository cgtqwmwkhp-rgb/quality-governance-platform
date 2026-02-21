# ADR-0016: Testing Strategy

**Status:** Accepted
**Date:** 2026-02-20
**Decision Makers:** Engineering Team

## Context

The platform accumulated tests of varying quality -- from robust interaction tests to trivial smoke checks (`expect(document.body).toBeTruthy()`) and import-only backend tests. Coverage thresholds were initially set conservatively at 45%, allowing significant gaps in critical business logic. A systematic testing strategy was needed to establish clear standards and drive coverage toward world-class levels.

## Decision

### Test Quality Standards

1. **No trivial assertions.** Every test must verify meaningful behavior:
   - Frontend: `screen.findByText()`, `screen.getByRole()`, `userEvent` interactions
   - Backend: Actual method calls with assertions on return values, side effects, or exceptions
   - E2E: Real DOM assertions -- no `expect(true).toBe(true)` patterns

2. **Service-level testing priority.** Domain services in `src/domain/services/` must have dedicated test files with:
   - Pure function tests for calculation/scoring logic (no DB required)
   - Mock-based tests for DB-dependent methods using `unittest.mock`
   - Edge case coverage (empty inputs, boundary values, invalid data)
   - Minimum 5 test cases per service

3. **Coverage threshold progression:**
   - Current: 55% statements / 40% branches / 25% functions / 55% lines (frontend); 55% backend
   - Target: 70% statements / 55% branches / 40% functions / 70% lines (frontend); 70% backend
   - Thresholds are enforced in CI and documented in `CONTRIBUTING.md`

### Test Pyramid

| Layer | Tool | Scope | Blocking in CI |
|-------|------|-------|----------------|
| Unit (backend) | pytest + pytest-cov | Service logic, models, utilities | Yes (55% gate) |
| Unit (frontend) | Vitest + @vitest/coverage-v8 | Components, hooks, utilities | Yes (55/40/25/55%) |
| Integration | pytest + httpx AsyncClient | API endpoints with DB | Yes (55% gate) |
| E2E (backend) | pytest + TestClient | Full request cycles | Yes (baseline gate) |
| E2E (frontend) | Playwright | User journeys | Yes |

### Test Patterns

**Backend service tests:**
```python
import pytest
from unittest.mock import AsyncMock, MagicMock

class TestRiskScoringService:
    def test_calculate_risk_level_high(self):
        result = calculate_risk_level(likelihood=4, impact=5)
        assert result == "critical"

    @pytest.mark.asyncio
    async def test_get_statistics_empty(self):
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = await service.get_statistics(mock_db, tenant_id=1)
        assert result["total"] == 0
```

**Frontend component tests:**
```typescript
it('renders the heading and action buttons', async () => {
  render(<MemoryRouter><MyPage /></MemoryRouter>);
  expect(await screen.findByText('Page Title')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /create/i })).toBeInTheDocument();
});
```

## Consequences

**Positive:**
- All new tests verify real behavior, catching actual regressions
- Service-level tests enable safe refactoring of business logic
- Progressive threshold increases prevent coverage erosion

**Negative:**
- Higher maintenance burden for mock-heavy tests
- Initial effort to upgrade existing smoke tests

**Risks mitigated:**
- Tests catching real bugs before production
- Coverage gates prevent regression
- Living documentation of expected behavior

## References

- `vitest.config.ts` -- frontend coverage thresholds
- `.github/workflows/ci.yml` -- backend coverage gates
- `CONTRIBUTING.md` -- developer-facing testing requirements
