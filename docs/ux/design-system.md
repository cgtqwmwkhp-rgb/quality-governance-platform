# UX quality and information architecture (D02)

This document describes the design tokens, UI primitives, layout and interaction patterns, responsive behaviour, and dark mode for the Quality Governance Platform frontend.

## Design tokens

The file [`frontend/src/styles/design-tokens.css`](../../frontend/src/styles/design-tokens.css) defines global CSS custom properties used for spacing, semantic colour, typography, radii, shadows, motion, and z-index.

### Colours

- **Brand / semantic**: `--color-primary`, `--color-primary-hover`, `--color-primary-light`, `--color-secondary`, `--color-success`, `--color-warning`, `--color-danger`, `--color-info`, plus light variants where defined.
- **Neutrals**: `--color-bg`, `--color-bg-subtle`, `--color-bg-muted`, `--color-border`, `--color-border-strong`, `--color-text`, `--color-text-secondary`, `--color-text-muted`, `--color-text-inverse`.
- **Status badges**: `--color-status-open`, `--color-status-in-progress`, `--color-status-completed`, `--color-status-closed`, `--color-status-critical`, `--color-status-high`, `--color-status-medium`, `--color-status-low`.
- **Dark theme**: `.dark` overrides background, border, and text tokens for dark surfaces.

Application chrome also uses HSL-based tokens in [`frontend/src/index.css`](../../frontend/src/index.css) (for example `--primary`, `--background`, `--foreground`, chart colours) which Tailwind maps via `hsl(var(--…))`. Treat **design-tokens.css** as the documented spacing/radius/shadow scale; use **index.css** for the primary theme variable system consumed by Tailwind components.

### Spacing

4px-based scale: `--space-0` through `--space-20` (from `0` to `5rem`).

### Typography

- **Families**: `--font-sans` (Inter stack), `--font-mono` (JetBrains Mono).
- **Sizes**: `--text-xs` through `--text-3xl`.
- **Line height**: `--leading-tight`, `--leading-normal`, `--leading-relaxed`.
- **Weights**: `--weight-normal` through `--weight-bold`.

### Radii

`--radius-sm` through `--radius-full`.

### Shadows

`--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-xl`.

### Motion and elevation

- **Duration**: `--duration-fast`, `--duration-normal`, `--duration-slow`.
- **Easing**: `--easing-default`.
- **Z-index**: `--z-dropdown` through `--z-toast`.

## Component library

UI primitives live under `frontend/src/components/ui/`. The following are the canonical building blocks:

| Primitive | Role |
|-----------|------|
| **Button** | Primary actions, variants, loading/disabled states |
| **Card** | Grouped content, dashboard tiles |
| **Badge** | Status and metadata chips |
| **Input** | Text fields with validation styling |
| **Textarea** | Multi-line input |
| **Dialog** | Modal dialogs (Radix-based) |
| **Select** | Dropdown selection |
| **Tooltip** | Contextual hints (`TooltipProvider` in app shell) |
| **Avatar** | User or entity avatars |
| **Breadcrumbs** | Hierarchy wayfinding |
| **EmptyState** | Zero-data messaging and next steps |
| **Skeleton** | Loading placeholders |
| **Switch** | Boolean toggles |
| **ThemeToggle** | Light/dark/system preference control |
| **Label** | Accessible labels for form controls |
| **DataTable** | Tabular data with sorting/filtering patterns |
| **Tabs** | Sectioned detail views |
| **Toast** | Transient feedback (`ToastProvider` in app shell) |
| **LiveAnnouncer** | Screen-reader announcements for dynamic updates |

## Layout patterns

- **Sidebar navigation**: Primary app navigation grouped by domain (core, workforce, governance, library, enterprise, admin) in `Layout` and related shells.
- **Breadcrumb trails**: Used on deeper pages to preserve hierarchy and quick upward navigation.
- **Card grids**: Dashboards and summary views use responsive grids of cards/tiles.
- **Detail pages with tabs**: Record detail views split into sections (overview, activity, related records) using tabs where appropriate.

## Interaction patterns

- **Loading**: Route-level spinners, skeletons for slow data, and disabled buttons during mutations.
- **Empty**: EmptyState components with short rationale and a primary action (create, adjust filters, clear search).
- **Error**: Inline field errors, toast or banner for API failures, and route-level error boundaries for isolated failures.
- **Confirmation**: Dialogs for destructive actions (delete, irreversible transitions).
- **Toast notifications**: Success and failure feedback for mutations and background operations.

## Responsive design

- **Mobile-first**: Base styles target small viewports; layouts expand with breakpoints.
- **Breakpoints**: Follow Tailwind defaults (`sm`, `md`, `lg`, `xl`, `2xl`) as configured in [`frontend/tailwind.config.js`](../../frontend/tailwind.config.js).
- **Touch targets**: Interactive controls use padding and min sizes appropriate for touch (prefer at least ~44×44px effective target for primary actions on mobile).

## Dark mode

- **ThemeToggle**: [`frontend/src/components/ui/ThemeToggle.tsx`](../../frontend/src/components/ui/ThemeToggle.tsx) cycles or selects light/dark/system; preference is stored in `localStorage` (`qgp-theme`).
- **ThemeProvider**: [`frontend/src/contexts/ThemeContext.tsx`](../../frontend/src/contexts/ThemeContext.tsx) applies `light` or `dark` class on `document.documentElement` and updates theme-colour meta for mobile browsers.
- **CSS variables**: Light and dark values are defined in `:root` and `.dark` in **design-tokens.css** and the HSL token blocks in **index.css**, enabling consistent token-driven theming across components.
