# WCAG 2.1 AA Compliance Checklist

> Quality Governance Platform — Accessibility Target: **WCAG 2.1 Level AA**
>
> Last reviewed: 2026-03-07

## Automated Checks (CI-enforced)

| # | Criterion | Tool | Status |
|---|-----------|------|--------|
| 1 | `jsx-a11y` ESLint plugin (all rules at warn+) | ESLint | Active |
| 2 | `axe-core` violations in component tests | vitest + jest-axe | Active |
| 3 | Radix UI primitives used for interactive elements | Code review | Active |
| 4 | Lighthouse accessibility score >= 95 | @lhci/cli (`lighthouserc.json` minScore 0.95) | Active |

## Perceivable (1.x)

- [x] **1.1.1** Non-text Content — All `<img>` tags require `alt` (eslint jsx-a11y/alt-text)
- [x] **1.3.1** Info and Relationships — Semantic HTML used (headings, lists, tables, landmarks)
- [x] **1.3.4** Orientation — Responsive layouts behave in portrait and landscape without loss of essential functionality on primary flows
- [x] **1.4.1** Use of Color — Status indicators use icon + text, not color alone
- [x] **1.4.3** Contrast (Minimum) — Design tokens target 4.5:1 (text) / 3:1 (large text); axe contrast rules in CI; some badges/charts still need token pass (see Known Exceptions / VPAT)
- [x] **1.4.4** Resize Text — Content remains usable at 200% browser zoom on main employee and authenticated dashboards (responsive typography)
- [x] **1.4.11** Non-text Contrast — Verified — Radix UI primitives meet 3:1 non-text contrast ratio by default
- [ ] **1.4.13** Content on Hover or Focus — **Note:** Dismissible / hoverable / persistent behaviour not exhaustively verified on every tooltip, popover, and submenu (Radix patterns cover key components)

## Operable (2.x)

- [x] **2.1.1** Keyboard — All functionality via keyboard (Radix primitives)
- [x] **2.1.2** No Keyboard Trap — Focus can always move away
- [ ] **2.2.1** Timing Adjustable — **Note:** Session extension / timeout warning copy and behaviour not yet verified end-to-end against live auth configuration
- [x] **2.4.1** Bypass Blocks — Skip-to-content link present
- [x] **2.4.2** Page Titled — Each route has descriptive `<title>`
- [x] **2.4.3** Focus Order — Logical tab order
- [x] **2.4.4** Link Purpose — Link text is descriptive
- [x] **2.4.6** Headings and Labels — Descriptive headings
- [x] **2.4.7** Focus Visible — Focus ring visible on interactive elements (Tailwind / design-system focus styles); dark mode and dense layouts still tightened per VPAT
- [x] **2.5.3** Label in Name — Verified — all interactive controls use visible label text matching accessible name

## Understandable (3.x)

- [x] **3.1.1** Language of Page — `<html lang="en">` set
- [ ] **3.1.2** Language of Parts — **Note:** N/A for current English-only release; mark `lang` on fragments when Welsh/Polish or other locales ship (roadmap)
- [x] **3.2.1** On Focus — No context change on focus
- [x] **3.2.2** On Input — No auto-submission without warning
- [x] **3.3.1** Error Identification — Form errors described in text
- [x] **3.3.2** Labels or Instructions — All inputs have visible labels
- [ ] **3.3.3** Error Suggestion — Partial — form validation provides suggestions; legacy forms pending migration
- [ ] **3.3.4** Error Prevention (Legal/Financial) — **Note:** Confirm-before-submit not verified for all high-impact admin / bulk destructive flows — UAT pass TBD

## Robust (4.x)

- [x] **4.1.1** Parsing — Valid HTML output
- [x] **4.1.2** Name, Role, Value — Radix UI provides proper ARIA
- [x] **4.1.3** Status Messages — Toast notifications use `role="status"`

## Testing Procedures

### Manual Test Protocol (monthly)

1. Navigate all primary flows using keyboard only (Tab, Enter, Escape, Arrow keys)
2. Test with screen reader (VoiceOver on macOS, NVDA on Windows)
3. Zoom to 200% and verify no content is lost
4. Disable CSS and verify content structure is logical
5. Test with high-contrast mode enabled

### Automated CI Pipeline

```yaml
# In .github/workflows/ci.yml frontend-tests job:
- name: Lint frontend (eslint + jsx-a11y)
  run: npx eslint src/ --max-warnings 0

- name: Run frontend tests (includes axe-core)
  run: npx vitest run --coverage --passWithNoTests
```

## Known Exceptions

| Component | Issue | Justification | Target Fix |
|-----------|-------|---------------|------------|
| Risk Matrix Heatmap | Color-only encoding | Tooltip + cell label provide text alternative | v2.1 |
| Chart components | Complex SVG | Provide data table alternative | v2.2 |

## Resources

- [WCAG 2.1 Quick Reference](https://www.w3.org/WAI/WCAG21/quickref/)
- [Radix UI Accessibility](https://www.radix-ui.com/docs/primitives/overview/accessibility)
- [axe-core Rules](https://github.com/dequelabs/axe-core/blob/develop/doc/rule-descriptions.md)
