export type AssuranceCertReadinessStatus = 'valid' | 'due_soon' | 'expired' | 'unknown'

export type AssuranceCertShelfItem = {
  shelf_key: string
  name: string
  scheme: string
  source: string
  issuing_body?: string | null
  reference_number?: string | null
  expiry_date?: string | null
  readiness_status: AssuranceCertReadinessStatus
  is_critical: boolean
  is_external_sor: boolean
  detail_path?: string | null
  library_path?: string | null
  external_url?: string | null
  metadata?: Record<string, unknown>
}

export type AssuranceCertShelfResponse = {
  items: AssuranceCertShelfItem[]
  total: number
  summary: {
    valid: number
    due_soon: number
    expired: number
    unknown: number
    by_scheme: Record<string, number>
  }
  due_soon_days: number
}
