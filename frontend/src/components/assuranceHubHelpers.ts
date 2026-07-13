import type { AuditRun } from '../api/client'

/** Query param value for the Customer Audits assurance filter on `/audits`. */
export const ASSURANCE_SOURCE_CUSTOMER = 'customer'

/** Canonical Audits URL for the Customer Audits assurance view (IA-W3). */
export const CUSTOMER_AUDITS_AUDITS_PATH = `/audits?source=${ASSURANCE_SOURCE_CUSTOMER}`

type CustomerAuditLike = Pick<AuditRun, 'source_origin' | 'assurance_scheme'> & {
  external_audit_type?: string
}

/** True when an audit run belongs to the customer / external assurance slice. */
export function isCustomerAssuranceAudit(audit: CustomerAuditLike): boolean {
  if (audit.source_origin === 'customer') return true
  if (audit.external_audit_type === 'customer') return true
  const scheme = (audit.assurance_scheme || '').trim().toLowerCase()
  return scheme.includes('customer audit') || scheme === 'customer'
}

/** Filter audit runs to the assurance source slice when `source` is set. */
export function filterAuditsByAssuranceSource(
  audits: AuditRun[],
  source: string | null,
): AuditRun[] {
  if (source === ASSURANCE_SOURCE_CUSTOMER) {
    return audits.filter(isCustomerAssuranceAudit)
  }
  return audits
}

/** Sidebar active-state helper — disambiguates `/audits` vs customer filter query. */
export function navItemIsActive(itemPath: string, pathname: string, search = ''): boolean {
  const [targetPath, targetQuery = ''] = itemPath.split('?')

  if (pathname !== targetPath && !pathname.startsWith(`${targetPath}/`)) {
    if (itemPath === CUSTOMER_AUDITS_AUDITS_PATH && pathname === '/customer-audits') {
      return true
    }
    return false
  }

  if (targetQuery) {
    if (pathname !== targetPath) return false
    const expected = new URLSearchParams(targetQuery)
    const actual = new URLSearchParams(search)
    for (const [key, value] of expected.entries()) {
      if (actual.get(key) !== value) return false
    }
    return true
  }

  if (targetPath === '/audits' && pathname === '/audits') {
    return new URLSearchParams(search).get('source') !== ASSURANCE_SOURCE_CUSTOMER
  }

  return pathname === targetPath || pathname.startsWith(`${targetPath}/`)
}
