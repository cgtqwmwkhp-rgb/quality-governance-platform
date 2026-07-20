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

export const ASSURANCE_CERT_SCHEME_LABELS: Record<string, string> = {
  register: 'Compliance register',
  planet_mark: 'Planet Mark',
  uvdb_achilles: 'UVDB Achilles',
  library: 'Governance Library',
}

export const ASSURANCE_CERT_READINESS_LABELS: Record<AssuranceCertReadinessStatus, string> = {
  valid: 'Valid',
  due_soon: 'Due soon',
  expired: 'Expired',
  unknown: 'Unknown',
}

export const ASSURANCE_CERT_READINESS_COLORS: Record<AssuranceCertReadinessStatus, string> = {
  valid: 'bg-success/10 text-success',
  due_soon: 'bg-warning/10 text-warning',
  expired: 'bg-destructive/10 text-destructive',
  unknown: 'bg-muted text-muted-foreground',
}

export function formatAssuranceCertExpiry(expiryDate?: string | null): string {
  if (!expiryDate) return 'No expiry recorded'
  const parsed = new Date(expiryDate)
  if (Number.isNaN(parsed.getTime())) return expiryDate
  return parsed.toLocaleDateString()
}
