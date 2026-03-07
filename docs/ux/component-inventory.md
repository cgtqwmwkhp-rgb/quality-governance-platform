# Component Inventory — Quality Governance Platform

> Last updated: 2026-03-07

## 1. Existing UI Primitives

All primitives live in `frontend/src/components/ui/`.

| Component | Library | Props / Variants | Notes |
|-----------|---------|-----------------|-------|
| **Button** | CVA | `variant`: default, destructive, outline, secondary, ghost, link; `size`: sm, default, lg, icon | Primary CTA component |
| **Input** | Native | `error` prop for validation styling | No label integration |
| **Textarea** | Native | `error` prop for validation styling | No character counter |
| **Card** | Native | CardHeader, CardTitle, CardContent, CardFooter sub-components | Composable card system |
| **Badge** | CVA | Many variants: status colours, priority colours | Used for status indicators |
| **Dialog** | Radix | DialogTrigger, DialogContent, DialogHeader, DialogFooter | Accessible modal |
| **Select** | Radix | SelectTrigger, SelectContent, SelectItem | Accessible dropdown |
| **Switch** | Radix | Standard toggle | Boolean inputs |
| **Tooltip** | Radix | TooltipTrigger, TooltipContent | Hover/focus hints |
| **ThemeToggle** | Custom | Light/dark mode toggle | Persisted in preferences store |
| **LiveAnnouncer** | Custom | Announces content changes to screen readers | Accessibility utility |
| **SetupRequiredPanel** | Custom | Type guard + empty state for unconfigured modules | Specific to tenant setup |

## 2. Missing Primitives (recommended additions)

| Component | Priority | Rationale |
|-----------|----------|-----------|
| **Label** | High | Forms currently lack semantic `<label>` association via a shared component; required for WCAG 2.1 AA |
| **Skeleton** | High | Loading states use spinners; skeleton screens provide better perceived performance |
| **Toast / Sonner** | High | No notification toast system for success/error feedback after mutations |
| **DataTable** | High | List views are ad-hoc; a shared paginated, sortable, filterable table would reduce code and improve consistency |
| **Pagination** | Medium | Used alongside DataTable; currently bespoke per page |
| **DropdownMenu** | Medium | Context menus on list rows (edit, delete, view) |
| **Alert** | Medium | Inline alert banners for form validation and page-level warnings |
| **Avatar** | Low | User identity display in nav and comments |
| **Tabs** | Medium | Module detail views (e.g., risk → controls / assessments / KRIs) |
| **Breadcrumb** | Medium | Navigation context; recommended in IA audit |
| **Command** | Low | Keyboard-first command palette (Cmd+K) |

## 3. Design Tokens

A design tokens file has been created at `frontend/src/styles/design-tokens.css`. It defines:

- **Spacing scale** (4px base, 0–80px)
- **Semantic colours** (primary, success, warning, danger, info + neutral palette)
- **Status badge colours** (open, in-progress, completed, critical, etc.)
- **Typography** (Inter font family, size scale, weights)
- **Border radii** (sm through full)
- **Shadows** (sm, md, lg, xl)
- **Transitions** (duration + easing)
- **Z-index scale** (dropdown through toast)
- **Dark theme overrides**

Import in `main.tsx`:

```typescript
import "./styles/design-tokens.css";
```

## 4. Component Quality Checklist

For each new or updated primitive:

- [ ] Uses design tokens (no hardcoded colours or spacing)
- [ ] Accepts `className` prop for composition
- [ ] Uses `React.forwardRef` for ref forwarding
- [ ] Has TypeScript props interface exported
- [ ] Renders semantic HTML elements
- [ ] Passes `eslint-plugin-jsx-a11y` rules
- [ ] Tested with `axe-core` (via `jest-axe`)
- [ ] Keyboard navigable (Tab, Enter, Escape)
- [ ] Works in both light and dark themes
- [ ] Documented in this inventory

## 5. Next Steps

1. Add `Label`, `Skeleton`, and `Toast` components (Week 1).
2. Build `DataTable` with pagination, sorting, and filtering (Week 2).
3. Set up Storybook for component documentation and visual regression.
4. Create a component playground page in the admin UI for internal reference.
