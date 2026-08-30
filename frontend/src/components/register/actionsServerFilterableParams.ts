/**
 * Query names GET /api/v1/actions/ applies in SQL, and the /actions URL params
 * that never reach it.
 *
 * `register` is the caption key from PEL-HSEQ-5062. It selects a banner, not
 * rows: no action source carries a PEL reference, so PEL-PROC-5014's Open shows
 * the whole action register with a caption over it, not a slavery subset.
 *
 * The page's `view` chip is in neither list on purpose — it is translated into
 * the `assigned_to` and `overdue` server params rather than sent as `view`.
 * `sourceType` / `sourceId` are likewise the URL spelling of `source_type` /
 * `source_id`.
 */

export const ACTIONS_SERVER_FILTERABLE_PARAMS = [
  'page',
  'page_size',
  'status',
  'source_type',
  'source_id',
  'source_reference',
  'assigned_to',
  'overdue',
  'asset_id',
] as const

export const ACTIONS_CLIENT_ONLY_PARAMS = ['register', 'returnTo', 'create'] as const
