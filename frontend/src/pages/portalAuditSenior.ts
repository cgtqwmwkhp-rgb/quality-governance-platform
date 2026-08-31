import { hasRole, isSuperuser } from '../utils/auth'

/** App roles that may use the portal published-audit catalogue. Not workforce_roles. */
export const PORTAL_AUDIT_SENIOR_ROLES = ['admin', 'manager', 'supervisor', 'superadmin'] as const

export function isPortalAuditSenior(): boolean {
  if (isSuperuser()) return true
  return hasRole(...PORTAL_AUDIT_SENIOR_ROLES)
}
