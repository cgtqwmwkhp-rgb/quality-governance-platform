/**
 * Shared portal submit success helpers — staff golden-thread vs tracking-ref honesty.
 */

export interface PortalSubmitSuccessFields {
  reference_number: string
  tracking_code?: string | null
  can_open_staff_record?: boolean
  staff_href?: string | null
  entity_id?: number | null
  entity_type?: string | null
  triage_assigned?: boolean
}

export function portalTriageRoutedHint(fields: PortalSubmitSuccessFields): string | null {
  if (!fields.triage_assigned) {
    return null
  }
  return 'Your report has been routed to a case owner for review.'
}

export function canOfferStaffDeepLink(fields: PortalSubmitSuccessFields): boolean {
  return Boolean(fields.can_open_staff_record && fields.staff_href)
}

export function portalStaffRecordLabel(entityType?: string | null): string {
  switch (entityType) {
    case 'near_miss':
      return 'Open near-miss record'
    case 'incident':
      return 'Open incident record'
    case 'complaint':
      return 'Open complaint record'
    case 'rta':
      return 'Open RTA record'
    default:
      return 'Open staff record'
  }
}
