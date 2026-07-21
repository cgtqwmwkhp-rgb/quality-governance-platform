/**
 * Safety Asset Register API client — wraps `/api/v1/assets` + locations.
 * Separate from workforceClient (AM-FE lane; zero overlap with WF-CLIENT).
 */
import api from './client'

export type ExpiryBand = 'overdue' | 'due_30' | 'due_60' | 'due_90'

export interface SafetyAssetType {
  id: number
  category: string
  name: string
  description?: string | null
  icon?: string | null
  is_active: boolean
  tenant_id?: number | null
  created_at?: string
  updated_at?: string
}

export interface SafetyLocation {
  id: number
  name: string
  kind: string
  parent_id?: number | null
  is_active: boolean
  tenant_id?: number | null
  created_at?: string
  updated_at?: string
}

export interface SafetyAsset {
  id: number
  external_id: string
  asset_type_id: number
  asset_number: string
  name: string
  description?: string | null
  make?: string | null
  model?: string | null
  serial_number?: string | null
  year_of_manufacture?: number | null
  safe_working_load?: number | null
  swl_unit?: string | null
  status: string
  last_service_date?: string | null
  next_service_due?: string | null
  last_loler_date?: string | null
  next_loler_due?: string | null
  site?: string | null
  department?: string | null
  location_id?: number | null
  vehicle_reg?: string | null
  owner_user_id?: number | null
  expiry_date?: string | null
  photo_evidence_id?: number | null
  qr_code_data?: string | null
  metadata_json?: Record<string, unknown> | null
  tenant_id?: number | null
  created_at: string
  updated_at: string
}

export interface SafetyAssetListParams {
  page?: number
  page_size?: number
  search?: string
  asset_type_id?: number
  status?: string
  site?: string
  location_id?: number
  vehicle_reg?: string
  owner_user_id?: number
  expiry_band?: ExpiryBand
}

export interface SafetyAssetListResponse {
  items: SafetyAsset[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface SafetyAssetTypeListResponse {
  items: SafetyAssetType[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface SafetyLocationListResponse {
  items: SafetyLocation[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface SafetyAssetUpdate {
  asset_type_id?: number
  asset_number?: string
  name?: string
  description?: string | null
  make?: string | null
  model?: string | null
  serial_number?: string | null
  status?: string
  location_id?: number | null
  vehicle_reg?: string | null
  owner_user_id?: number | null
  expiry_date?: string | null
  photo_evidence_id?: number | null
  qr_code_data?: string | null
  site?: string | null
  department?: string | null
}

export interface CesAssetImportIssue {
  row: number
  code: string
  message: string
  field?: string | null
  severity: 'error' | 'warning'
}

export interface CesAssetImportReport {
  dry_run: boolean
  total_rows: number
  valid_rows: number
  error_rows: number
  creates: number
  updates: number
  ok: boolean
  errors: CesAssetImportIssue[]
  warnings: CesAssetImportIssue[]
  preview: Array<{
    row: number
    action: 'create' | 'update'
    asset_number: string
    name: string
    serial_number: string
    owner_user_id?: number | null
    location_id?: number | null
    vehicle_reg?: string | null
    status: string
    not_made_available: boolean
  }>
}

export interface CesAssetImportCommitResult {
  created_count: number
  updated_count: number
  created_asset_ids: number[]
  updated_asset_ids: number[]
  report: CesAssetImportReport
}

/** KPI metrics — null means unavailable (never silent-zero on fetch failure). */
export type MetricValue = number | null

export interface SafetyAssetKpis {
  total: MetricValue
  in_date: MetricValue
  due_30: MetricValue
  due_60: MetricValue
  due_90: MetricValue
  overdue: MetricValue
  quarantined: MetricValue
}

export const EMPTY_SAFETY_ASSET_KPIS: SafetyAssetKpis = {
  total: null,
  in_date: null,
  due_30: null,
  due_60: null,
  due_90: null,
  overdue: null,
  quarantined: null,
}

function totalFromSettled(
  result: PromiseSettledResult<{ data: { total: number } }>,
): MetricValue {
  if (result.status !== 'fulfilled') return null
  const total = result.value.data?.total
  return typeof total === 'number' && Number.isFinite(total) ? total : null
}

const BASE = '/api/v1/assets'

export const safetyAssetsApi = {
  listAssets: (params?: SafetyAssetListParams) =>
    api.get<SafetyAssetListResponse>(`${BASE}/`, { params }),

  getAsset: (id: number) => api.get<SafetyAsset>(`${BASE}/${id}`),

  updateAsset: (id: number, data: SafetyAssetUpdate) =>
    api.patch<SafetyAsset>(`${BASE}/${id}`, data),

  cesImportDryRun: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    // Full CES workbooks are large; allow long parse/validate wall-clock.
    return api.post<CesAssetImportReport>('/api/v1/asset-imports/ces/dry-run', form, {
      timeout: 300000,
    })
  },

  cesImportCommit: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    // Commit upserts ~1.8k rows; keep above default 45s write timeout.
    return api.post<CesAssetImportCommitResult>('/api/v1/asset-imports/ces/commit', form, {
      timeout: 300000,
    })
  },

  listAssetTypes: (params?: {
    page?: number
    page_size?: number
    search?: string
    category?: string
    is_active?: boolean
  }) => api.get<SafetyAssetTypeListResponse>(`${BASE}/asset-types`, { params }),

  listLocations: (params?: {
    page?: number
    page_size?: number
    kind?: string
    is_active?: boolean
    parent_id?: number
    search?: string
  }) => api.get<SafetyLocationListResponse>(`${BASE}/locations`, { params }),

  getLocation: (id: number) => api.get<SafetyLocation>(`${BASE}/locations/${id}`),

  /**
   * Parallel count queries for the KPI hub.
   * Each metric is independently settled — failures yield null, never fake zeros.
   */
  getKpis: async (
    baseFilters?: Omit<SafetyAssetListParams, 'page' | 'page_size' | 'expiry_band' | 'status'>,
  ): Promise<SafetyAssetKpis> => {
    const shared = { ...baseFilters, page: 1, page_size: 1 }
    const [
      totalRes,
      overdueRes,
      due30Res,
      due60Res,
      due90Res,
      quarantinedRes,
    ] = await Promise.allSettled([
      safetyAssetsApi.listAssets(shared),
      safetyAssetsApi.listAssets({ ...shared, expiry_band: 'overdue' }),
      safetyAssetsApi.listAssets({ ...shared, expiry_band: 'due_30' }),
      safetyAssetsApi.listAssets({ ...shared, expiry_band: 'due_60' }),
      safetyAssetsApi.listAssets({ ...shared, expiry_band: 'due_90' }),
      safetyAssetsApi.listAssets({ ...shared, status: 'quarantined' }),
    ])

    const total = totalFromSettled(totalRes)
    const overdue = totalFromSettled(overdueRes)
    const in_date =
      total != null && overdue != null ? Math.max(0, total - overdue) : null

    return {
      total,
      in_date,
      due_30: totalFromSettled(due30Res),
      due_60: totalFromSettled(due60Res),
      due_90: totalFromSettled(due90Res),
      overdue,
      quarantined: totalFromSettled(quarantinedRes),
    }
  },
}
