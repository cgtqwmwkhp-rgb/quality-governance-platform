import { describe, expect, it } from 'vitest'
import {
  groupJobCellLinksByKind,
  isExternalJobCellLink,
  jobCellLinkKindLabel,
  jobCellLinkOpenTarget,
  jobCellLinkRel,
  resolveJobCellLinkHref,
  shouldShowJobCellLinks,
} from '../jobCellLinksHelpers'
import type { JobCellLink } from '../../api/jobLifecycleClient'

const link = (overrides: Partial<JobCellLink> & Pick<JobCellLink, 'kind' | 'href'>): JobCellLink => ({
  id: 1,
  tenant_id: 1,
  cell_id: 2,
  label: 'Example',
  sort_order: 0,
  created_at: '2026-08-08T00:00:00Z',
  updated_at: '2026-08-08T00:00:00Z',
  ...overrides,
})

describe('jobCellLinksHelpers', () => {
  it('requires both job_lifecycle and job_cell_links', () => {
    expect(shouldShowJobCellLinks(false, true)).toBe(false)
    expect(shouldShowJobCellLinks(true, false)).toBe(false)
    expect(shouldShowJobCellLinks(true, true)).toBe(true)
  })

  it('labels kinds and treats external as new-tab', () => {
    expect(jobCellLinkKindLabel('app')).toBe('App')
    expect(jobCellLinkKindLabel('external')).toBe('External')
    expect(jobCellLinkKindLabel('audit_outcome')).toBe('Audit')
    expect(isExternalJobCellLink({ kind: 'external' })).toBe(true)
    expect(jobCellLinkOpenTarget({ kind: 'external' })).toBe('_blank')
    expect(jobCellLinkRel({ kind: 'external' })).toBe('noopener noreferrer')
    expect(jobCellLinkOpenTarget({ kind: 'app' })).toBeUndefined()
  })

  it('uses server href and never invents SPA paths for app/audit', () => {
    expect(
      resolveJobCellLinkHref(
        link({ kind: 'app', href: '/documents/7', entity_type: 'document', entity_id: 7 }),
      ),
    ).toBe('/documents/7')
    expect(
      resolveJobCellLinkHref(
        link({ kind: 'audit_outcome', href: '/audits/12/execute', audit_run_id: 12 }),
      ),
    ).toBe('/audits/12/execute')
    expect(
      resolveJobCellLinkHref(
        link({ kind: 'external', href: '', external_url: 'https://example.test/x' }),
      ),
    ).toBe('https://example.test/x')
  })

  it('groups links by kind', () => {
    const grouped = groupJobCellLinksByKind([
      link({ id: 1, kind: 'app', href: '/documents/1' }),
      link({ id: 2, kind: 'external', href: 'https://x.test' }),
      link({ id: 3, kind: 'audit_outcome', href: '/audits/1/execute' }),
      link({ id: 4, kind: 'app', href: '/risk-register/9' }),
    ])
    expect(grouped.app).toHaveLength(2)
    expect(grouped.external).toHaveLength(1)
    expect(grouped.audit_outcome).toHaveLength(1)
  })
})
