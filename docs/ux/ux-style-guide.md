# UX Style Guide

**Owner**: Frontend Engineering
**Last Updated**: 2026-04-03
**Review Cycle**: Quarterly

---

## Design Principles

1. **Clarity over cleverness** — every screen should communicate its purpose within 3 seconds.
2. **Consistency** — reuse shared components and design tokens across all pages.
3. **Accessibility first** — WCAG 2.1 AA compliance as a baseline, not an afterthought.
4. **Progressive disclosure** — show essential information first, with details available on demand.
5. **Responsive by default** — all layouts must work from 320px to 2560px viewport widths.

---

## Color System

Colors are defined as CSS custom properties (design tokens) in `frontend/src/index.css` and referenced via Tailwind utility classes.

| Token | Purpose | Light Mode | Dark Mode |
|-------|---------|------------|-----------|
| `--background` | Page background | `hsl(0 0% 100%)` | `hsl(222.2 84% 4.9%)` |
| `--foreground` | Primary text | `hsl(222.2 84% 4.9%)` | `hsl(210 40% 98%)` |
| `--primary` | Brand actions, links | `hsl(221.2 83.2% 53.3%)` | `hsl(217.2 91.2% 59.8%)` |
| `--card` | Card backgrounds | `hsl(0 0% 100%)` | `hsl(222.2 84% 4.9%)` |
| `--muted` | Disabled/secondary text | `hsl(210 40% 96.1%)` | `hsl(217.2 32.6% 17.5%)` |
| `--destructive` | Error/danger states | `hsl(0 84.2% 60.2%)` | `hsl(0 62.8% 30.6%)` |
| `--border` | Borders and dividers | `hsl(214.3 31.8% 91.4%)` | `hsl(217.2 32.6% 17.5%)` |

### Contrast Requirements

- Text on `--background`: minimum 4.5:1 contrast ratio (WCAG AA).
- Interactive elements: minimum 3:1 contrast ratio against adjacent colors.
- Focus indicators: visible ring with `--ring` token, minimum 3:1 contrast.

---

## Typography

| Element | Font | Size | Weight | Line Height |
|---------|------|------|--------|-------------|
| Page title (h1) | System sans-serif | 1.875rem (30px) | 700 | 1.2 |
| Section heading (h2) | System sans-serif | 1.5rem (24px) | 600 | 1.3 |
| Subsection (h3) | System sans-serif | 1.25rem (20px) | 600 | 1.4 |
| Body text | System sans-serif | 0.875rem (14px) | 400 | 1.5 |
| Small / caption | System sans-serif | 0.75rem (12px) | 400 | 1.4 |
| Code / monospace | `ui-monospace, monospace` | 0.875rem | 400 | 1.5 |

---

## Spacing Scale

Based on a 4px base unit, applied via Tailwind spacing utilities:

| Token | Value | Usage |
|-------|-------|-------|
| `space-1` | 4px | Inline padding, icon gaps |
| `space-2` | 8px | Compact spacing |
| `space-3` | 12px | Standard component padding |
| `space-4` | 16px | Card padding, section gaps |
| `space-6` | 24px | Section separation |
| `space-8` | 32px | Page-level margins |

---

## Component Guidelines

### Buttons

- **Primary**: Use `--primary` background for the main call-to-action on a page. Limit to one per visible section.
- **Secondary/Outline**: Use for supporting actions.
- **Destructive**: Red (`--destructive`) for delete/remove actions. Always require confirmation.
- **Ghost**: Use for navigation or low-emphasis actions within toolbars.
- **Disabled state**: Reduce opacity to 0.5; remove pointer events.

### Cards

- Background: `--card` token.
- Border: `--border` token, 1px solid, `rounded-lg` (8px).
- Shadow: `shadow-sm` for elevation.
- Padding: `space-4` (16px) for content, `space-3` (12px) for header/footer.

### Forms

- Labels above inputs (never inline for accessibility).
- Required fields marked with visual indicator and `aria-required="true"`.
- Validation errors shown below the input with `--destructive` color.
- Input height: 40px (consistent touch target).

### Tables

- Use `DataTable` component with sortable columns, pagination, and empty state.
- Zebra striping optional (use `--muted` at 50% opacity).
- Row actions in a trailing column or contextual menu.

### Modals / Dialogs

- Use `AlertDialog` for destructive confirmations.
- Maximum width: 480px for forms, 640px for content.
- Always include a visible close button and Escape key handler.

---

## Iconography

- Icon set: Lucide React icons (consistent with shadcn/ui).
- Size: 16px for inline, 20px for buttons, 24px for navigation.
- Always pair icons with text labels (or `aria-label` for icon-only buttons).

---

## Responsive Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Mobile | < 640px | Single column, stacked navigation |
| Tablet | 640px–1024px | Two-column, collapsible sidebar |
| Desktop | > 1024px | Full sidebar, multi-column layouts |

---

## Related Documents

- [`docs/ux/design-system.md`](design-system.md) — design system overview
- [`docs/ux/component-inventory.md`](component-inventory.md) — component catalog
- [`docs/accessibility/a11y-coverage-matrix.md`](../accessibility/a11y-coverage-matrix.md) — accessibility status
- [`frontend/src/index.css`](../../frontend/src/index.css) — CSS custom properties
- [`frontend/tailwind.config.js`](../../frontend/tailwind.config.js) — Tailwind configuration
