export type {
  AssuranceCertReadinessStatus,
  AssuranceCertShelfItem,
  AssuranceCertShelfResponse,
} from '../api/assuranceCertShelfTypes'

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
