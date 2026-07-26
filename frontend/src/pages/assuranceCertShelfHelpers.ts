import type { AssuranceCertReadinessStatus } from '../api/assuranceCertShelfTypes'

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

export type CertShelfEmptyKind = 'filtered' | 'unpopulated'

/**
 * PX-243: distinguish a filter miss from an unpopulated shelf so operators do
 * not read "Valid 0" as reassurance that certificates exist elsewhere.
 */
export function buildCertShelfEmptyCopy(input: {
  schemeFilter: string
  statusFilter: string
}): { kind: CertShelfEmptyKind; title: string; description: string } {
  const filtersActive = input.schemeFilter !== 'all' || input.statusFilter !== 'all'
  if (filtersActive) {
    return {
      kind: 'filtered',
      title: 'No certificates match these filters',
      description:
        'Clear the scheme or readiness filter to see the full shelf. An empty filtered view is not the same as an unpopulated register.',
    }
  }
  return {
    kind: 'unpopulated',
    title: 'No certificates on the shelf yet',
    description:
      'No certificates are recorded in any scheme — this is an unpopulated shelf, not a filter result. Add register certificates in Monitoring, record Planet Mark / UVDB expiry dates in their modules, or file statutory masters in the Governance Library with an expiry date.',
  }
}
