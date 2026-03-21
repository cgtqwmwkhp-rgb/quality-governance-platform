# UI component inventory

This document lists shared UI primitives under `frontend/src/components/ui/`. Paths are relative to the repository root.

**Axe coverage:** Components exercised in `frontend/src/components/ui/__tests__/a11y.test.tsx` are marked **tested**; others are **untested** for automated axe-core checks.

---

## AlertDialog

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/AlertDialog.tsx` |
| **Exports** | `AlertDialog`, `AlertDialogTrigger`, `AlertDialogPortal`, `AlertDialogOverlay`, `AlertDialogContent`, `AlertDialogHeader`, `AlertDialogFooter`, `AlertDialogTitle`, `AlertDialogDescription`, `AlertDialogAction`, `AlertDialogCancel` |
| **Key props** | Re-exports Radix `Dialog` root props (`open`, `defaultOpen`, `onOpenChange`, etc.); content/trigger inherit Radix dialog content/trigger props |
| **Variants** | N/A (composition of `Dialog` primitives with `role="alertdialog"` on content) |
| **a11y status** | **tested** (axe: open dialog with title, description, action, cancel) |

---

## Avatar

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Avatar.tsx` |
| **Exports** | `Avatar` |
| **Key props** | `size` (`sm` \| `md` \| `lg` \| `xl`), `src`, `alt`, `fallback`, standard div/button HTML attributes (interactive when `onClick` is set) |
| **Variants** | Sizes only |
| **a11y status** | **untested** |

---

## Badge

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Badge.tsx` |
| **Exports** | `Badge`, type `BadgeVariant` |
| **Key props** | `variant` (default, secondary, destructive, success, warning, info, outline, status/priority presets), `className`, HTML div attributes |
| **Variants** | Many `variant` options via CVA |
| **a11y status** | **tested** |

---

## Breadcrumbs

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Breadcrumbs.tsx` |
| **Exports** | `Breadcrumbs`, type `BreadcrumbItem` |
| **Key props** | `items` (`{ label, href? }[]`), `className` |
| **Variants** | N/A |
| **a11y status** | **untested** |

---

## Button

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Button.tsx` |
| **Exports** | `Button`, `buttonVariants` |
| **Key props** | `variant`, `size`, `disabled`, standard button HTML attributes |
| **Variants** | `variant`: default, destructive, outline, secondary, ghost, link, success, warning; `size`: default, sm, lg, xl, icon, icon-sm, icon-lg |
| **a11y status** | **tested** |

---

## Card

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Card.tsx` |
| **Exports** | `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter` |
| **Key props** | `Card`: `hoverable`, layout/HTML attributes; subcomponents: standard HTML attributes for their elements |
| **Variants** | `hoverable` on `Card` |
| **a11y status** | **tested** |

---

## Checkbox

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Checkbox.tsx` |
| **Exports** | `Checkbox` |
| **Key props** | Radix checkbox root props: `checked`, `onCheckedChange`, `disabled`, `required`, `name`, `value`, `id`, `className`, etc. |
| **Variants** | N/A |
| **a11y status** | **tested** (with `Label`) |

---

## DataTable

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/DataTable.tsx` |
| **Exports** | `DataTable`, type `Column`, type `DataTableProps` |
| **Key props** | `columns`, `data`, `keyExtractor`, `caption`, `emptyMessage`, `loading`, `stickyHeader`, `onRowClick`, `className` |
| **Variants** | N/A |
| **a11y status** | **tested** (populated and empty) |

---

## Dialog

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Dialog.tsx` |
| **Exports** | `Dialog`, `DialogTrigger`, `DialogPortal`, `DialogClose`, `DialogOverlay`, `DialogContent`, `DialogHeader`, `DialogFooter`, `DialogTitle`, `DialogDescription` |
| **Key props** | Radix dialog root/content/trigger props |
| **Variants** | N/A |
| **a11y status** | **untested** (covered indirectly via `AlertDialog`, which wraps the same primitives) |

---

## DropdownMenu

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/DropdownMenu.tsx` |
| **Exports** | `DropdownMenu`, `DropdownMenuTrigger`, `DropdownMenuContent`, `DropdownMenuItem`, `DropdownMenuSeparator` |
| **Key props** | Radix dropdown root/trigger/content/item props (`defaultOpen`, `open`, `onOpenChange`, `sideOffset`, `disabled`, etc.) |
| **Variants** | N/A |
| **a11y status** | **tested** |

---

## EmptyState

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/EmptyState.tsx` |
| **Exports** | `EmptyState` |
| **Key props** | `title`, `description`, `icon`, `action`, `className` |
| **Variants** | N/A |
| **a11y status** | **tested** |

---

## Input

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Input.tsx` |
| **Exports** | `Input` |
| **Key props** | `error`, standard `input` attributes (`type`, `id`, `placeholder`, `disabled`, etc.) |
| **Variants** | Error styling via `error` |
| **a11y status** | **tested** (with `Label`, required) |

---

## Label

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Label.tsx` |
| **Exports** | `Label` |
| **Key props** | `required` (visual asterisk), `htmlFor`, standard label attributes |
| **Variants** | N/A |
| **a11y status** | **tested** (with `Input` / `Switch`) |

---

## ProgressBar

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/ProgressBar.tsx` |
| **Exports** | `ProgressBar`, `progressBarTrackVariants` |
| **Key props** | `value`, `max`, `variant` (default, success, warning, destructive), `size` (sm, md, lg), wrapper HTML attributes |
| **Variants** | `variant`, `size` via CVA |
| **a11y status** | **tested** |

---

## RadioGroup

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/RadioGroup.tsx` |
| **Exports** | `RadioGroup`, `RadioGroupItem` |
| **Key props** | `RadioGroup`: `value`, `onValueChange`, layout props; `RadioGroupItem`: `value`, `disabled`, `id`, plus attributes forwarded to the native `input` |
| **Variants** | N/A |
| **a11y status** | **tested** (two items with labels) |

---

## Select

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Select.tsx` |
| **Exports** | `Select`, `SelectGroup`, `SelectValue`, `SelectTrigger`, `SelectContent`, `SelectLabel`, `SelectItem`, `SelectSeparator`, scroll buttons |
| **Key props** | Radix select props on root/trigger/content/items (`value`, `defaultValue`, `onValueChange`, `open`, `disabled`, `position`, etc.) |
| **Variants** | N/A |
| **a11y status** | **tested** |

---

## SkeletonLoader (`SkeletonLoader.tsx`)

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/SkeletonLoader.tsx` |
| **Exports** | `Skeleton`, `TableSkeleton`, `CardSkeleton` |
| **Key props** | `Skeleton`: `lines`, `variant` (`text` \| `card` \| `table`), `className`; `TableSkeleton`: `rows`, `columns`, `className`; `CardSkeleton`: `count`, `className` |
| **Variants** | `Skeleton.variant` switches layout |
| **a11y status** | **untested** |

---

## Switch

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Switch.tsx` |
| **Exports** | `Switch` |
| **Key props** | Radix switch root props (`checked`, `onCheckedChange`, `disabled`, `id`, `aria-label`, etc.) |
| **Variants** | N/A |
| **a11y status** | **tested** |

---

## Tabs

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Tabs.tsx` |
| **Exports** | `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` |
| **Key props** | Radix tabs root/list/trigger/content props (`value`, `defaultValue`, `onValueChange`, `orientation`, etc.) |
| **Variants** | N/A |
| **a11y status** | **tested** |

---

## Textarea

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Textarea.tsx` |
| **Exports** | `Textarea` |
| **Key props** | `error`, standard `textarea` attributes |
| **Variants** | Error styling via `error` |
| **a11y status** | **untested** |

---

## ThemeToggle

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/ThemeToggle.tsx` |
| **Exports** | `ThemeToggle` |
| **Key props** | `variant` (`icon` \| `full`), `className` |
| **Variants** | `icon` (single toggle) vs `full` (light/dark/system) |
| **a11y status** | **untested** |

---

## Tooltip

| | |
| --- | --- |
| **File** | `frontend/src/components/ui/Tooltip.tsx` |
| **Exports** | `TooltipProvider`, `Tooltip`, `TooltipTrigger`, `TooltipContent` |
| **Key props** | Radix tooltip provider/root/trigger/content props (`delayDuration`, `sideOffset`, `side`, etc.) |
| **Variants** | N/A |
| **a11y status** | **untested** |

---

## Summary

| Component | Axe in `a11y.test.tsx` |
| --- | --- |
| AlertDialog | Yes |
| Badge | Yes |
| Button | Yes |
| Card | Yes |
| Checkbox | Yes |
| DataTable | Yes |
| DropdownMenu | Yes |
| EmptyState | Yes |
| Input | Yes |
| Label | Yes |
| ProgressBar | Yes |
| RadioGroup / RadioGroupItem | Yes |
| Select | Yes |
| Switch | Yes |
| Tabs | Yes |
| Avatar, Breadcrumbs, Dialog, SkeletonLoader, Textarea, ThemeToggle, Tooltip | No |
