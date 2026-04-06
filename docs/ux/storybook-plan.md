# Storybook Plan (D02)

Plan for implementing Storybook as the component documentation and development tool.

## Objective

Provide an interactive component catalog for all shared UI components, enabling:
- Visual regression testing
- Component-level documentation
- Design system enforcement
- Developer onboarding

## Component Coverage (Current)

**26 stories** currently exist under `frontend/src/components/ui/`:

| Category | Total Components | Storybook Stories | Coverage |
|----------|-----------------|-------------------|----------|
| Layout (Tabs, Breadcrumbs, ThemeToggle) | ~5 | 3 | 60% |
| Form Controls (Input, Select, Checkbox, RadioGroup, Switch, Textarea, Label) | ~15 | 7 | 47% |
| Data Display (DataTable, Card, Badge, Avatar, Tooltip) | ~10 | 5 | 50% |
| Feedback (Toast, AlertDialog, Dialog, EmptyState, ProgressBar, LoadingSkeleton, SkeletonLoader, LiveAnnouncer) | ~8 | 8 | 100% |
| Domain-Specific (SetupRequiredPanel, DropdownMenu, Button) | ~20 | 3 | 15% |

**Phase 1**: 26 of ~38 shared/reusable components covered (68%).

## Implementation Steps

| Step | Action | Status |
|------|--------|--------|
| 1 | Install `@storybook/react-vite` and dependencies | Done |
| 2 | Create `.storybook/main.ts` with Vite config | Done |
| 3 | Create `.storybook/preview.ts` with theme providers | Done |
| 4 | Write stories for Layout components | Done (3/5) |
| 5 | Write stories for Form components | Done (7/15) |
| 6 | Write stories for Data Display components | Done (5/10) |
| 7 | Write stories for Feedback components | Done (8/8) |
| 8 | Add Storybook build to CI (optional gate) | Planned |

## Configuration

Minimal `.storybook/main.ts`:

```typescript
import type { StorybookConfig } from '@storybook/react-vite';

const config: StorybookConfig = {
  stories: ['../src/**/*.stories.@(ts|tsx)'],
  addons: ['@storybook/addon-essentials'],
  framework: '@storybook/react-vite',
};

export default config;
```

## Related Documents

- [`docs/ux/ux-style-guide.md`](ux-style-guide.md) — UX design standards
- [`frontend/src/components/ui/`](../../frontend/src/components/ui/) — shared UI components
