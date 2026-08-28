/** Query names GET /incidents applies in SQL. Status/severity are client-only. */

export const INCIDENT_SERVER_FILTERABLE_PARAMS = [
  'page',
  'page_size',
  'reporter_email',
  'owner',
  'ids',
  'search',
  'type',
  'asset_id',
] as const

export const INCIDENT_CLIENT_ONLY_PARAMS = ['status', 'severity', 'q', 'register'] as const
