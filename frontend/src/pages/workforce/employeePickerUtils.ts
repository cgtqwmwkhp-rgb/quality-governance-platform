import type { EngineerProfile } from '../../api/client'

/** Shared list params for assessment/training employee pickers — active roster only. */
export const ACTIVE_EMPLOYEES_LIST_PARAMS = {
  page: '1',
  page_size: '500',
  is_active: 'true',
} as const

export function employeePrimaryLabel(
  eng: Pick<EngineerProfile, 'id' | 'display_name' | 'employee_number' | 'job_title'>,
): string {
  return (
    eng.display_name?.trim() ||
    eng.employee_number?.trim() ||
    eng.job_title?.trim() ||
    `Employee #${eng.id}`
  )
}

/** Skills matrix row label — prefer display name over employee number / raw id (PX-238). */
export function matrixEngineerLabel(
  eng: Pick<{ engineer_id: number; display_name?: string | null; employee_number?: string | null }, 'engineer_id' | 'display_name' | 'employee_number'>,
): string {
  return (
    eng.display_name?.trim() ||
    eng.employee_number?.trim() ||
    `Employee #${eng.engineer_id}`
  )
}

/** Role-aware picker label: primary name with job title / department when available. */
export function employeePickerOptionLabel(
  eng: Pick<
    EngineerProfile,
    'id' | 'display_name' | 'employee_number' | 'job_title' | 'department'
  >,
): string {
  const primary = employeePrimaryLabel(eng)
  const roleParts: string[] = []
  const jobTitle = eng.job_title?.trim()
  const department = eng.department?.trim()
  if (jobTitle && jobTitle !== primary) roleParts.push(jobTitle)
  if (department) roleParts.push(department)
  if (roleParts.length === 0) return primary
  return `${primary} — ${roleParts.join(' · ')}`
}

export function buildEmployeeLabelMap(engineers: EngineerProfile[]): Record<number, string> {
  const map: Record<number, string> = {}
  for (const eng of engineers) {
    map[eng.id] = employeePickerOptionLabel(eng)
  }
  return map
}

export function sortEmployeesForPicker(engineers: EngineerProfile[]): EngineerProfile[] {
  return [...engineers].sort((a, b) =>
    employeePickerOptionLabel(a).localeCompare(employeePickerOptionLabel(b)),
  )
}

/** Payload for investigation lead / CAPA assignee pickers (PX-168). */
export type InvestigationAssigneePayload = {
  assignee_id?: number
  assignee_email?: string
  assignee_name?: string
}

/**
 * Resolve EngineerPeoplePicker selection for investigations/actions.
 * Roster-only employees (no portal login) are assignable by display name;
 * linked employees resolve to user id + email for notifications.
 */
export function resolveInvestigationAssigneeSelection(selection: {
  label: string
  user?: { id: number; email: string }
} | null): InvestigationAssigneePayload {
  if (!selection) return {}
  if (selection.user?.id != null) {
    return {
      assignee_id: selection.user.id,
      assignee_email: selection.user.email,
    }
  }
  const name = selection.label.trim()
  return name ? { assignee_name: name } : {}
}
