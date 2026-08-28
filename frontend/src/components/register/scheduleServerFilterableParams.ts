/** Query names GET /compliance-schedule/requirements applies server-side. */

export const SCHEDULE_SERVER_FILTERABLE_PARAMS = [
  'page',
  'page_size',
  'is_active',
  'location_id',
  'status',
  'statutory',
] as const

export const SCHEDULE_CLIENT_ONLY_PARAMS = ['clause', 'framework', 'register', 'view'] as const

export function parseStatutoryParam(raw: string | null): boolean | undefined {
  if (raw === 'true') return true
  if (raw === 'false') return false
  return undefined
}
