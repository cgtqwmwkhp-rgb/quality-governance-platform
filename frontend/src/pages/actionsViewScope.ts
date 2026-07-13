/**
 * Pure helpers for Actions My Work / Overdue server-scope wiring.
 * Kept free of React so unit tests do not depend on full-page load races.
 */

export type ActionsViewMode = 'all' | 'my' | 'overdue' | 'my_overdue'

export type ActionsListScope = {
  assigned_to?: string
  overdue?: boolean
}

/** Map URL `view` query param → view mode (unknown → all). */
export function parseActionsViewParam(raw: string | null | undefined): ActionsViewMode {
  if (raw === 'my' || raw === 'overdue' || raw === 'my_overdue') return raw
  return 'all'
}

/** Build list API scope for Mine / Overdue / Mine+Overdue. */
export function buildActionsListScope(viewMode: ActionsViewMode): ActionsListScope {
  switch (viewMode) {
    case 'my':
      return { assigned_to: 'me', overdue: undefined }
    case 'overdue':
      return { assigned_to: undefined, overdue: true }
    case 'my_overdue':
      return { assigned_to: 'me', overdue: true }
    default:
      return { assigned_to: undefined, overdue: undefined }
  }
}

export function actionsViewRequiresIdentity(viewMode: ActionsViewMode): boolean {
  return viewMode === 'my' || viewMode === 'my_overdue'
}

export function actionsViewUsesServerFilter(viewMode: ActionsViewMode): boolean {
  return viewMode !== 'all'
}
