import { describe, expect, it } from 'vitest'
import type { AuditRun } from '../../api/client'
import {
  buildCustomerAuditsSummary,
  filterCustomerAssuranceRuns,
  getCustomerAuditWorkspacePath,
  isExternalAuditImportRun,
  parseCustomerAuditsSection,
} from '../customerAuditsHelpers'

const baseRun = (overrides: Partial<AuditRun> = {}): AuditRun =>
  ({
    id: 1,
    reference_number: 'AUD-001',
    template_id: 1,
    template_version: 1,
    status: 'scheduled',
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }) as AuditRun

describe('customerAuditsHelpers', () => {
  it('parseCustomerAuditsSection defaults to runs', () => {
    expect(parseCustomerAuditsSection(null)).toBe('runs')
    expect(parseCustomerAuditsSection('findings')).toBe('findings')
    expect(parseCustomerAuditsSection('invalid')).toBe('runs')
  })

  it('filterCustomerAssuranceRuns keeps customer slice only', () => {
    const runs = [
      baseRun({ id: 1, source_origin: 'customer' }),
      baseRun({ id: 2, source_origin: 'internal' }),
      baseRun({ id: 3, assurance_scheme: 'Customer Audit' }),
    ]
    expect(filterCustomerAssuranceRuns(runs).map((run) => run.id)).toEqual([1, 3])
  })

  it('buildCustomerAuditsSummary aggregates counts', () => {
    const runs = [
      baseRun({ id: 1, status: 'in_progress', source_document_asset_id: 10 }),
      baseRun({ id: 2, status: 'completed' }),
      baseRun({ id: 3, status: 'pending_review' }),
    ]
    const summary = buildCustomerAuditsSummary(runs, 2)
    expect(summary.total).toBe(3)
    expect(summary.inProgress).toBe(1)
    expect(summary.completed).toBe(1)
    expect(summary.pendingReview).toBe(1)
    expect(summary.openFindings).toBe(2)
    expect(summary.withSourceDoc).toBe(1)
  })

  it('getCustomerAuditWorkspacePath routes import runs to review workspace', () => {
    expect(getCustomerAuditWorkspacePath(baseRun())).toBe('/audits/1/execute')
    expect(
      getCustomerAuditWorkspacePath(
        baseRun({ is_external_audit_import: true }),
        99,
      ),
    ).toBe('/audits/1/import-review?jobId=99')
  })

  it('isExternalAuditImportRun detects intake flags', () => {
    expect(isExternalAuditImportRun(baseRun())).toBe(false)
    expect(isExternalAuditImportRun(baseRun({ is_external_import_intake: true }))).toBe(true)
  })
})
