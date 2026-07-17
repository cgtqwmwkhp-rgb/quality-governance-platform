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
