import { describe, expect, it } from 'vitest'
import {
  ASSURANCE_SOURCE_CUSTOMER,
  CUSTOMER_AUDITS_AUDITS_PATH,
  filterAuditsByAssuranceSource,
  isCustomerAssuranceAudit,
  navItemIsActive,
} from '../assuranceHubHelpers'
import type { AuditRun } from '../../api/client'

const baseAudit = {
  id: 1,
  reference_number: 'AUD-00001',
  template_id: 1,
  template_version: 1,
  status: 'scheduled' as const,
  created_at: '2026-01-01T00:00:00Z',
}

describe('assuranceHubHelpers', () => {
  it('exposes the customer assurance filter path', () => {
    expect(CUSTOMER_AUDITS_AUDITS_PATH).toBe('/audits?source=customer')
    expect(ASSURANCE_SOURCE_CUSTOMER).toBe('customer')
  })

  it('isCustomerAssuranceAudit matches customer metadata', () => {
    expect(isCustomerAssuranceAudit({ ...baseAudit, source_origin: 'customer' })).toBe(true)
    expect(isCustomerAssuranceAudit({ ...baseAudit, external_audit_type: 'customer' })).toBe(
      true,
    )
    expect(
      isCustomerAssuranceAudit({ ...baseAudit, assurance_scheme: 'Customer Audit' }),
    ).toBe(true)
    expect(isCustomerAssuranceAudit({ ...baseAudit, source_origin: 'internal' })).toBe(false)
  })

  it('filterAuditsByAssuranceSource returns customer slice only', () => {
    const audits = [
      { ...baseAudit, id: 1, source_origin: 'customer' },
      { ...baseAudit, id: 2, source_origin: 'internal' },
      { ...baseAudit, id: 3, assurance_scheme: 'Customer Audit' },
    ] satisfies AuditRun[]

    expect(filterAuditsByAssuranceSource(audits, ASSURANCE_SOURCE_CUSTOMER)).toHaveLength(2)
    expect(filterAuditsByAssuranceSource(audits, null)).toHaveLength(3)
  })

  it('navItemIsActive separates all-audits from customer filter', () => {
    expect(navItemIsActive('/audits', '/audits', '')).toBe(true)
    expect(navItemIsActive('/audits', '/audits', '?source=customer')).toBe(false)
    expect(navItemIsActive(CUSTOMER_AUDITS_AUDITS_PATH, '/audits', '?source=customer')).toBe(
      true,
    )
    expect(navItemIsActive(CUSTOMER_AUDITS_AUDITS_PATH, '/customer-audits', '')).toBe(true)
    expect(navItemIsActive('/audits', '/audits/41/execute', '')).toBe(true)
  })
})
