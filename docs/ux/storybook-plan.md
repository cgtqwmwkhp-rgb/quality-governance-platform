# Storybook Plan (D02)

Plan for implementing Storybook as the component documentation and development tool.

## Objective

Provide an interactive component catalog for all shared UI components, enabling:
- Visual regression testing
- Component-level documentation
- Design system enforcement
- Developer onboarding

## Component Coverage Target

| Category | Total Components | Storybook Stories | Coverage Target |
|----------|-----------------|-------------------|-----------------|
| Layout (Shell, Nav, Sidebar) | ~5 | 0 | 100% |
| Form Controls (Input, Select, Checkbox) | ~15 | 0 | 100% |
| Data Display (Table, Card, Badge) | ~10 | 0 | 100% |
| Feedback (Toast, Alert, Modal) | ~8 | 0 | 100% |
| Domain-Specific (AuditCard, RiskMatrix) | ~20 | 0 | 50% (P2) |

**Phase 1 Target**: All shared/reusable components (Layout + Form + Data + Feedback = ~38 components).

## Implementation Steps

| Step | Action | Status |
|------|--------|--------|
| 1 | Install `@storybook/react-vite` and dependencies | Planned |
| 2 | Create `.storybook/main.ts` with Vite config | Planned |
| 3 | Create `.storybook/preview.ts` with theme providers | Planned |
| 4 | Write stories for Layout components | Planned |
| 5 | Write stories for Form components | Planned |
| 6 | Write stories for Data Display components | Planned |
| 7 | Write stories for Feedback components | Planned |
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
