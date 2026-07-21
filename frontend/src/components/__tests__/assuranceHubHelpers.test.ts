import { describe, expect, it } from 'vitest'
import {
  ACHILLES_UVDB_AUDITS_PATH,
  ASSURANCE_SOURCE_ACHILLES,
  ASSURANCE_SOURCE_CUSTOMER,
  ASSURANCE_SOURCE_UVDB,
  CUSTOMER_AUDITS_AUDITS_PATH,
  CUSTOMER_AUDITS_PROGRAMME_PATH,
  UVDB_AUDITS_AUDITS_PATH,
  filterAuditsByAssuranceSource,
  getCustomerCapaActionsPath,
  getCustomerRiskRegisterPath,
  getUvdbCapaActionsPath,
  getUvdbRiskRegisterPath,
  isAchillesUvdbAssuranceAudit,
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
  it('exposes the customer assurance filter path and programme home', () => {
    expect(CUSTOMER_AUDITS_AUDITS_PATH).toBe('/audits?source=customer')
    expect(CUSTOMER_AUDITS_PROGRAMME_PATH).toBe('/customer-audits')
    expect(ASSURANCE_SOURCE_CUSTOMER).toBe('customer')
  })

  it('exposes Achilles / UVDB assurance filter paths with parity aliases', () => {
    expect(ACHILLES_UVDB_AUDITS_PATH).toBe('/audits?source=achilles')
    expect(UVDB_AUDITS_AUDITS_PATH).toBe('/audits?source=uvdb')
    expect(ASSURANCE_SOURCE_ACHILLES).toBe('achilles')
    expect(ASSURANCE_SOURCE_UVDB).toBe('uvdb')
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

  it('isAchillesUvdbAssuranceAudit matches Achilles / UVDB / Verify metadata', () => {
    expect(
      isAchillesUvdbAssuranceAudit({ ...baseAudit, assurance_scheme: 'Achilles UVDB Verify B2' }),
    ).toBe(true)
    expect(isAchillesUvdbAssuranceAudit({ ...baseAudit, external_audit_type: 'uvdb' })).toBe(true)
    expect(isAchillesUvdbAssuranceAudit({ ...baseAudit, source_origin: 'achilles' })).toBe(true)
    expect(isAchillesUvdbAssuranceAudit({ ...baseAudit, source_origin: 'customer' })).toBe(false)
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

  it('filterAuditsByAssuranceSource returns Achilles / UVDB slice for both aliases', () => {
    const audits = [
      { ...baseAudit, id: 1, assurance_scheme: 'Achilles UVDB' },
      { ...baseAudit, id: 2, source_origin: 'internal' },
      { ...baseAudit, id: 3, external_audit_type: 'verify_b2' },
    ] satisfies AuditRun[]

    expect(filterAuditsByAssuranceSource(audits, ASSURANCE_SOURCE_ACHILLES)).toHaveLength(2)
    expect(filterAuditsByAssuranceSource(audits, ASSURANCE_SOURCE_UVDB)).toHaveLength(2)
  })

  it('builds scoped CAPA and Risk deep-link paths', () => {
    expect(getCustomerCapaActionsPath(88)).toBe('/actions?sourceType=audit_finding&sourceId=88')
    expect(getCustomerRiskRegisterPath('AUD-C-001')).toBe(
      '/risk-register?auditOnly=1&auditRef=AUD-C-001',
    )
    expect(getUvdbCapaActionsPath()).toBe('/actions?sourceType=audit_finding')
    expect(getUvdbCapaActionsPath(501)).toBe('/actions?sourceType=audit_finding&sourceId=501')
    expect(getUvdbRiskRegisterPath('UVDB-2026-0001')).toBe(
      '/risk-register?auditOnly=1&auditRef=UVDB-2026-0001',
    )
    expect(getUvdbRiskRegisterPath()).toBe('/risk-register?triage=import')
  })

  it('navItemIsActive separates all-audits from customer filter', () => {
    expect(navItemIsActive('/audits', '/audits', '')).toBe(true)
    expect(navItemIsActive('/audits', '/audits', '?source=customer')).toBe(false)
    expect(navItemIsActive(CUSTOMER_AUDITS_AUDITS_PATH, '/audits', '?source=customer')).toBe(
      true,
    )
    expect(navItemIsActive(CUSTOMER_AUDITS_PROGRAMME_PATH, '/customer-audits', '')).toBe(true)
    expect(navItemIsActive(CUSTOMER_AUDITS_AUDITS_PATH, '/customer-audits', '')).toBe(true)
    expect(navItemIsActive('/audits', '/audits/41/execute', '')).toBe(true)
  })

  it('navItemIsActive treats Achilles and UVDB source aliases as the same slice', () => {
    expect(navItemIsActive(ACHILLES_UVDB_AUDITS_PATH, '/audits', '?source=achilles')).toBe(true)
    expect(navItemIsActive(ACHILLES_UVDB_AUDITS_PATH, '/audits', '?source=uvdb')).toBe(true)
    expect(navItemIsActive(UVDB_AUDITS_AUDITS_PATH, '/audits', '?source=achilles')).toBe(true)
    expect(navItemIsActive(ACHILLES_UVDB_AUDITS_PATH, '/uvdb', '')).toBe(true)
    expect(navItemIsActive('/audits', '/audits', '?source=achilles')).toBe(false)
  })

  it('navItemIsActive keeps Admin Console exact-only vs admin children', () => {
    expect(navItemIsActive('/admin', '/admin', '')).toBe(true)
    expect(navItemIsActive('/admin', '/admin/users', '')).toBe(false)
    expect(navItemIsActive('/admin', '/admin/forms', '')).toBe(false)
    expect(navItemIsActive('/admin/users', '/admin/users', '')).toBe(true)
    expect(navItemIsActive('/admin/forms', '/admin/forms/new', '')).toBe(true)
  })
})
