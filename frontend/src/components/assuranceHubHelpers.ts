import type { AuditRun } from '../api/client'

/** Query param value for the Customer Audits assurance filter on `/audits`. */
export const ASSURANCE_SOURCE_CUSTOMER = 'customer'

/** Query param value for Achilles / UVDB / Verify assurance filter on `/audits`. */
export const ASSURANCE_SOURCE_ACHILLES = 'achilles'

/** Alias query param for the same Achilles / UVDB assurance slice. */
export const ASSURANCE_SOURCE_UVDB = 'uvdb'

/** Programme home for Customer Audits (thin shell; filtered board on Audits). */
export const CUSTOMER_AUDITS_PROGRAMME_PATH = '/customer-audits'

/** Canonical Audits URL for the Customer Audits assurance view (IA-W3). */
export const CUSTOMER_AUDITS_AUDITS_PATH = `/audits?source=${ASSURANCE_SOURCE_CUSTOMER}`

/** Canonical Audits URL for Achilles / UVDB assurance view (parity with customer). */
export const ACHILLES_UVDB_AUDITS_PATH = `/audits?source=${ASSURANCE_SOURCE_ACHILLES}`

/** Alias Audits URL using `source=uvdb` (same filter slice as Achilles). */
export const UVDB_AUDITS_AUDITS_PATH = `/audits?source=${ASSURANCE_SOURCE_UVDB}`

type CustomerAuditLike = Pick<AuditRun, 'source_origin' | 'assurance_scheme'> & {
  external_audit_type?: string
}

type AchillesUvdbAuditLike = Pick<AuditRun, 'source_origin' | 'assurance_scheme'> & {
  external_audit_type?: string
}

const ACHILLES_UVDB_KEYWORDS = ['achilles', 'uvdb', 'verify', 'b2'] as const

/** True when an audit run belongs to the customer / external assurance slice. */
export function isCustomerAssuranceAudit(audit: CustomerAuditLike): boolean {
  if (audit.source_origin === 'customer') return true
  if (audit.external_audit_type === 'customer') return true
  const scheme = (audit.assurance_scheme || '').trim().toLowerCase()
  return scheme.includes('customer audit') || scheme === 'customer'
}

/** True when an audit run belongs to the Achilles / UVDB / Verify assurance slice. */
export function isAchillesUvdbAssuranceAudit(audit: AchillesUvdbAuditLike): boolean {
  const type = (audit.external_audit_type || '').trim().toLowerCase()
  if (ACHILLES_UVDB_KEYWORDS.some((kw) => type.includes(kw))) return true

  const scheme = (audit.assurance_scheme || '').trim().toLowerCase()
  if (ACHILLES_UVDB_KEYWORDS.some((kw) => scheme.includes(kw))) return true

  // Import intake marks Achilles/UVDB as third_party with scheme text above;
  // also accept explicit origin tags used by specialist sync.
  const origin = (audit.source_origin || '').trim().toLowerCase()
  if (origin === 'achilles' || origin === 'uvdb') return true

  return false
}

function isAchillesUvdbSource(source: string | null): boolean {
  return source === ASSURANCE_SOURCE_ACHILLES || source === ASSURANCE_SOURCE_UVDB
}

/** Filter audit runs to the assurance source slice when `source` is set. */
export function filterAuditsByAssuranceSource(
  audits: AuditRun[],
  source: string | null,
): AuditRun[] {
  if (source === ASSURANCE_SOURCE_CUSTOMER) {
    return audits.filter(isCustomerAssuranceAudit)
  }
  if (isAchillesUvdbSource(source)) {
    return audits.filter(isAchillesUvdbAssuranceAudit)
  }
  return audits
}

/** Scoped CAPA Actions path for customer / external audit downstream hand-off. */
export function getCustomerCapaActionsPath(sourceId?: number | null): string {
  if (sourceId != null && Number.isFinite(sourceId) && sourceId > 0) {
    return `/actions?sourceType=audit_finding&sourceId=${sourceId}`
  }
  return '/actions?sourceType=audit_finding'
}

/** Scoped Risk Register path for customer / external audit downstream hand-off. */
export function getCustomerRiskRegisterPath(auditRef?: string | null): string {
  const ref = (auditRef || '').trim()
  if (ref) {
    return `/risk-register?auditOnly=1&auditRef=${encodeURIComponent(ref)}`
  }
  return '/risk-register?triage=import'
}

/** Scoped CAPA Actions path for UVDB / Achilles downstream hand-off. */
export function getUvdbCapaActionsPath(sourceId?: number | null): string {
  if (sourceId != null && Number.isFinite(sourceId) && sourceId > 0) {
    return `/actions?sourceType=audit_finding&sourceId=${sourceId}`
  }
  return '/actions?sourceType=audit_finding'
}

/** Scoped Risk Register path for UVDB / Achilles downstream hand-off. */
export function getUvdbRiskRegisterPath(auditRef?: string | null): string {
  const ref = (auditRef || '').trim()
  if (ref) {
    return `/risk-register?auditOnly=1&auditRef=${encodeURIComponent(ref)}`
  }
  return '/risk-register?triage=import'
}

/** Sidebar active-state helper — disambiguates `/audits` vs assurance filter queries. */
export function navItemIsActive(itemPath: string, pathname: string, search = ''): boolean {
  const [targetPath, targetQuery = ''] = itemPath.split('?')

  if (pathname !== targetPath && !pathname.startsWith(`${targetPath}/`)) {
    if (
      (itemPath === CUSTOMER_AUDITS_PROGRAMME_PATH ||
        itemPath === CUSTOMER_AUDITS_AUDITS_PATH) &&
      pathname === '/customer-audits'
    ) {
      return true
    }
    if (
      (itemPath === ACHILLES_UVDB_AUDITS_PATH || itemPath === UVDB_AUDITS_AUDITS_PATH) &&
      pathname === '/uvdb'
    ) {
      return true
    }
    return false
  }

  if (targetQuery) {
    if (pathname !== targetPath) return false
    const expected = new URLSearchParams(targetQuery)
    const actual = new URLSearchParams(search)
    // Achilles and UVDB query aliases share the same assurance slice.
    if (isAchillesUvdbSource(expected.get('source'))) {
      return isAchillesUvdbSource(actual.get('source'))
    }
    for (const [key, value] of expected.entries()) {
      if (actual.get(key) !== value) return false
    }
    return true
  }

  if (targetPath === '/audits' && pathname === '/audits') {
    const source = new URLSearchParams(search).get('source')
    return source !== ASSURANCE_SOURCE_CUSTOMER && !isAchillesUvdbSource(source)
  }

  // Admin console is exact-only; child routes (/admin/users, /admin/forms, …) have their own items.
  if (targetPath === '/admin') {
    return pathname === '/admin'
  }

  return pathname === targetPath || pathname.startsWith(`${targetPath}/`)
}
