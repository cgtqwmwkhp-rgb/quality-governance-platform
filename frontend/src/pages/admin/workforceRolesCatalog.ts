/** Admin lookup category for workforce role codes (maps to engineer.job_title / role_key). */
export const WORKFORCE_ROLES_LOOKUP_CATEGORY = 'workforce_roles' as const

/**
 * Standard role codes documented for admins — not pre-seeded; configure via Lookup Tables.
 * Employee records store the chosen label on `job_title` (PAMS sync maps `role` → job_title).
 */
export const WORKFORCE_ROLE_CODE_HINTS = [
  { code: 'engineer', label: 'Engineer' },
  { code: 'field_engineer', label: 'Field Engineer' },
  { code: 'supervisor', label: 'Supervisor' },
  { code: 'process_scheduler', label: 'Process Scheduler' },
] as const

export function workforceRoleHintCodes(): string {
  return WORKFORCE_ROLE_CODE_HINTS.map((h) => h.code).join(', ')
}
