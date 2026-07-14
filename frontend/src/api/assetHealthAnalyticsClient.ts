/** Read-only asset health analytics API client. */
import api from './client'

export interface AssetHealthSummary {
  total: number
  expiry_bands: Record<string, number>
  by_type: Record<string, number>
  by_status: Record<string, number>
  generated_at: string
}

export const assetHealthAnalyticsApi = {
  getSummary: () => api.get<AssetHealthSummary>('/api/v1/asset-health/summary'),
}
