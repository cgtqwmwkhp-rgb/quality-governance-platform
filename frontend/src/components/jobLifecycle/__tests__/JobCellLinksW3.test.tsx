/**
 * JL-UX-W3 — audit-lapse cue in the Step links panel.
 *
 * The cue is server-computed and read-only. What is pinned here is the honest
 * fallback: a link whose run has no readable cadence must show "Unknown", and
 * a non-audit link must show no cue at all rather than a reassuring default.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import JobCellLinks from '../JobCellLinks'
import type { JobCellLink } from '../../../api/jobLifecycleClient'

const createCellLink = vi.fn()
const deleteCellLink = vi.fn()
const listLinkEntityTypes = vi.fn()

vi.mock('../../../api/client', () => ({
  jobLifecycleApi: {
    createCellLink: (...args: unknown[]) => createCellLink(...args),
    deleteCellLink: (...args: unknown[]) => deleteCellLink(...args),
    listLinkEntityTypes: (...args: unknown[]) => listLinkEntityTypes(...args),
  },
  getApiErrorMessage: (err: unknown) => (err as Error)?.message ?? 'error',
}))

const NOW = '2026-08-08T00:00:00Z'

function auditLink(overrides: Partial<JobCellLink> = {}): JobCellLink {
  return {
    id: 500,
    tenant_id: 1,
    cell_id: 100,
    kind: 'audit_outcome',
    label: 'Finding 12',
    audit_run_id: 5,
    audit_finding_id: 12,
    href: '/audits/runs/5/findings/12',
    sort_order: 0,
    created_at: NOW,
    updated_at: NOW,
    ...overrides,
  }
}

function renderLinks(initialLinks: JobCellLink[]) {
  return render(
    <MemoryRouter>
      <JobCellLinks
        jobTypeId={1}
        laneId={10}
        stepId={20}
        jobLifecycleEnabled
        jobCellLinksEnabled
        initialLinks={initialLinks}
        jobTypes={[]}
      />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  createCellLink.mockReset()
  deleteCellLink.mockReset()
  listLinkEntityTypes.mockReset()
  listLinkEntityTypes.mockResolvedValue({ data: { items: ['document'], total: 1 } })
})

describe('audit lapse cue', () => {
  it('renders a lapsed verdict from the server', async () => {
    renderLinks([
      auditLink({
        audit_lapse: {
          state: 'lapsed',
          reason: 'cadence_overdue',
          next_due_at: NOW,
          frequency: 'annually',
          frequency_days: 365,
        },
      }),
    ])
    const chip = await screen.findByTestId('job-cell-link-lapse-500')
    expect(chip).toHaveAttribute('data-lapse-state', 'lapsed')
    expect(chip).toHaveTextContent('Lapsed')
    expect(chip.getAttribute('title')).toMatch(/Repeat audit was due/)
  })

  it('renders an in-date verdict', async () => {
    renderLinks([
      auditLink({
        audit_lapse: {
          state: 'current',
          reason: 'within_cadence',
          next_due_at: NOW,
          frequency: 'annually',
          frequency_days: 365,
        },
      }),
    ])
    expect(await screen.findByTestId('job-cell-link-lapse-500')).toHaveTextContent('In date')
  })

  it('falls back to Unknown when the server sent no lapse', async () => {
    renderLinks([auditLink()])
    const chip = await screen.findByTestId('job-cell-link-lapse-500')
    expect(chip).toHaveAttribute('data-lapse-state', 'unknown')
    expect(chip).toHaveTextContent('Unknown')
  })

  it('explains an ad-hoc audit rather than implying it is in date', async () => {
    renderLinks([
      auditLink({
        audit_lapse: {
          state: 'unknown',
          reason: 'no_audit_cadence',
          last_completed_at: NOW,
          frequency: 'ad_hoc',
        },
      }),
    ])
    const chip = await screen.findByTestId('job-cell-link-lapse-500')
    expect(chip).toHaveTextContent('Unknown')
    expect(chip.getAttribute('title')).toMatch(/ad-hoc audits never lapse/i)
  })

  it('shows no cue on links that are not audit outcomes', async () => {
    renderLinks([
      {
        ...auditLink({ id: 501 }),
        kind: 'external',
        external_url: 'https://a.test',
        audit_run_id: null,
        audit_finding_id: null,
        href: 'https://a.test',
      },
    ])
    expect(await screen.findByTestId('job-cell-link-501')).toBeInTheDocument()
    expect(screen.queryByTestId('job-cell-link-lapse-501')).not.toBeInTheDocument()
  })
})
