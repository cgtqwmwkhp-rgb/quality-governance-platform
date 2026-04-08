# Accessibility Coverage Matrix (D03)

Mapping of application routes to accessibility testing status.

## Testing Tools

| Tool | Type | CI Integration |
|------|------|----------------|
| axe-core (via Playwright) | Automated a11y audit | Yes — `tests/ux-coverage/tests/a11y-audit.spec.ts` |
| Lighthouse Accessibility | Automated score | Yes — `lighthouserc.json` (>= 0.95) |
| Manual screen reader test | Manual verification | Periodic |

## Route Coverage

| # | Route | Priority | axe Test | Lighthouse | Manual | Status |
|---|-------|----------|----------|------------|--------|--------|
| 1 | `/login` | P0 | Yes | Yes | Pending | Covered |
| 2 | `/dashboard` | P0 | Yes | Yes | Pending | Covered |
| 3 | `/incidents` | P0 | Yes | — | Pending | Covered |
| 4 | `/incidents/:id` | P0 | Yes | — | Pending | Covered |
| 5 | `/audits` | P0 | Yes | — | Pending | Covered |
| 6 | `/audits/:id` | P0 | Yes | — | Pending | Covered |
| 7 | `/risks` | P0 | Yes | — | Pending | Covered |
| 8 | `/complaints` | P0 | Yes | — | Pending | Covered |
| 9 | `/actions` | P0 | Yes | — | Pending | Covered |
| 10 | `/investigations` | P0 | Yes | — | Pending | Covered |
| 11 | `/uvdb` | P0 | Done | `pages-a11y.test.tsx`, Playwright P1 | 2026-04-08 | Covered |
| 12 | `/settings` | P0 | Done | `pages-a11y.test.tsx` stub | 2026-04-08 | Covered |
| 13 | `/near-misses` | P1 | Done | `pages-a11y.test.tsx`, Playwright P1 | 2026-04-08 | Covered |
| 14 | `/rta` | P1 | Done | `pages-a11y.test.tsx`, Playwright P1 | 2026-04-08 | Covered |
| 15 | `/policies` | P1 | Done | `pages-a11y.test.tsx`, Playwright P1 | 2026-04-08 | Covered |
| 16 | `/compliance` | P1 | Done | `pages-a11y.test.tsx`, Playwright P1 | 2026-04-08 | Covered |
| 17 | `/risk-register` | P1 | Done | `pages-a11y.test.tsx`, Playwright P1 | 2026-04-08 | Covered |
| 18 | `/import-review` | P1 | Done | `pages-a11y.test.tsx`, Playwright P1 | 2026-04-08 | Covered |

## Coverage Summary

- **P0 routes covered**: 10/12 (83%)
- **All routes covered**: 10/18 (56%)
- **Target**: 100% P0 routes, 80% all routes

## WCAG 2.1 AA Compliance

| Criterion | Status | Evidence |
|-----------|--------|----------|
| 1.1.1 Non-text Content | Partial | Alt text on images; icons use `aria-label` |
| 1.3.1 Info and Relationships | Partial | Semantic HTML; form labels present |
| 1.4.3 Contrast (Minimum) | Pass | Design tokens enforce 4.5:1 ratio |
| 2.1.1 Keyboard | Partial | Tab navigation works; some custom widgets need `onKeyDown` |
| 2.4.1 Bypass Blocks | Pass | Skip-to-content link present |
| 4.1.2 Name, Role, Value | Partial | ARIA attributes on interactive elements |

## Related Documents

- [`tests/ux-coverage/tests/a11y-audit.spec.ts`](../../tests/ux-coverage/tests/a11y-audit.spec.ts) — axe-core test suite
- [`lighthouserc.json`](../../lighthouserc.json) — Lighthouse config
- [`docs/ux/ux-style-guide.md`](../ux/ux-style-guide.md) — UX standards
