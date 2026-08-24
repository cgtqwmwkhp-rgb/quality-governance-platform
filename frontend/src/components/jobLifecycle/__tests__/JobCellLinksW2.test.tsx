/**
 * JL-UX-W2 — `job_cycle` nesting in the Step links composer.
 *
 * Two things are pinned: the JobType picker never offers the active cycle
 * (self-nesting is rejected server-side, so the UI must not invite it), and
 * the app entity-type dropdown comes from the server's href_registry with a
 * usable fallback when that GET fails.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import JobCellLinks from '../JobCellLinks'
import {
  FALLBACK_APP_ENTITY_TYPES,
  isJobCycleNestLink,
  jobCellLinkKindLabel,
  normaliseAppEntityTypes,
} from '../jobCellLinksHelpers'
import type { JobType } from '../../../api/jobLifecycleClient'

const createCellLink = vi.fn()
const deleteCellLink = vi.fn()
const listLinkEntityTypes = vi.fn()

vi.mock('../../../api/client', () => ({
  jobLifecycleApi: {
    createCellLink: (...args: unknown[]) => createCellLink(...args),
    deleteCellLink: (...args: unknown[]) => deleteCellLink(...args),
    listLinkEntityTypes: (...args: unknown[]) => listLinkEntityTypes(...args),
  },
  getApiErrorMessage: (err: unknown) =>
    (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
    (err as Error)?.message ??
    'error',
}))

const NOW = '2026-08-08T00:00:00Z'

function jobType(id: number, name: string): JobType {
  return {
    id,
    tenant_id: 1,
    code: name.toLowerCase(),
    name,
    sort_order: id,
    is_active: true,
    created_at: NOW,
    updated_at: NOW,
  }
}

function renderLinks(props: Partial<React.ComponentProps<typeof JobCellLinks>> = {}) {
  return render(
    <MemoryRouter>
      <JobCellLinks
        jobTypeId={1}
        laneId={10}
        stepId={20}
        jobLifecycleEnabled
        jobCellLinksEnabled
        jobTypes={[jobType(1, 'Operational'), jobType(2, 'Engineer'), jobType(3, 'Commissioning')]}
        {...props}
      />
    </MemoryRouter>,
  )
}

describe('JobCellLinks job_cycle nesting', () => {
  beforeEach(() => {
    createCellLink.mockReset()
    deleteCellLink.mockReset()
    listLinkEntityTypes.mockReset()
    listLinkEntityTypes.mockResolvedValue({ data: { items: ['document', 'risk'], total: 2 } })
  })

  it('offers a nested-cycle kind alongside the JL-3 kinds', async () => {
    renderLinks()
    expect(await screen.findByTestId('job-cell-links-kind-job_cycle')).toBeInTheDocument()
    expect(screen.getByTestId('job-cell-links-kind-app')).toBeInTheDocument()
    expect(screen.getByTestId('job-cell-links-kind-external')).toBeInTheDocument()
    expect(screen.getByTestId('job-cell-links-kind-audit_outcome')).toBeInTheDocument()
  })

  it('excludes the active cycle from the nest picker', async () => {
    renderLinks()
    fireEvent.click(await screen.findByTestId('job-cell-links-kind-job_cycle'))
    const picker = screen.getByTestId('job-cell-links-target-job-type') as HTMLSelectElement
    const values = Array.from(picker.options).map((o) => o.value)
    expect(values).not.toContain('1')
    expect(values).toContain('2')
    expect(values).toContain('3')
  })

  it('creates a nest link with target_job_type_id and no other refs', async () => {
    createCellLink.mockResolvedValue({
      data: {
        id: 55,
        tenant_id: 1,
        cell_id: 9,
        kind: 'job_cycle',
        label: 'Engineer pack',
        target_job_type_id: 2,
        href: '/job-lifecycle/cycles/2',
        sort_order: 0,
        created_at: NOW,
        updated_at: NOW,
      },
    })

    renderLinks()
    fireEvent.click(await screen.findByTestId('job-cell-links-kind-job_cycle'))
    fireEvent.change(screen.getByTestId('job-cell-links-label'), {
      target: { value: 'Engineer pack' },
    })
    fireEvent.change(screen.getByTestId('job-cell-links-target-job-type'), {
      target: { value: '2' },
    })
    fireEvent.click(screen.getByTestId('job-cell-links-add'))

    await waitFor(() => {
      expect(createCellLink).toHaveBeenCalledWith(1, 10, 20, {
        kind: 'job_cycle',
        label: 'Engineer pack',
        target_job_type_id: 2,
      })
    })
    expect(await screen.findByTestId('job-cell-link-55')).toHaveTextContent('Engineer pack')
  })

  it('refuses to POST a nest link with no target selected', async () => {
    renderLinks()
    fireEvent.click(await screen.findByTestId('job-cell-links-kind-job_cycle'))
    fireEvent.change(screen.getByTestId('job-cell-links-label'), { target: { value: 'Nowhere' } })
    fireEvent.click(screen.getByTestId('job-cell-links-add'))

    expect(await screen.findByTestId('job-cell-links-error')).toHaveTextContent(
      /need a target job cycle/i,
    )
    expect(createCellLink).not.toHaveBeenCalled()
  })

  it('surfaces the server 409 when a nest would create a cycle', async () => {
    createCellLink.mockRejectedValue({
      response: { status: 409, data: { detail: 'job_cycle link would create a nesting cycle' } },
    })

    renderLinks()
    fireEvent.click(await screen.findByTestId('job-cell-links-kind-job_cycle'))
    fireEvent.change(screen.getByTestId('job-cell-links-label'), { target: { value: 'Loop' } })
    fireEvent.change(screen.getByTestId('job-cell-links-target-job-type'), {
      target: { value: '2' },
    })
    fireEvent.click(screen.getByTestId('job-cell-links-add'))

    expect(await screen.findByTestId('job-cell-links-error')).toHaveTextContent(
      /would create a nesting cycle/i,
    )
  })

  it('says so when there is no other cycle to nest', async () => {
    renderLinks({ jobTypes: [jobType(1, 'Operational')] })
    fireEvent.click(await screen.findByTestId('job-cell-links-kind-job_cycle'))
    expect(screen.getByTestId('job-cell-links-target-job-type')).toHaveTextContent(
      /No other job cycles/i,
    )
  })
})

describe('app entity-type dropdown from href_registry', () => {
  beforeEach(() => {
    createCellLink.mockReset()
    listLinkEntityTypes.mockReset()
  })

  it('populates from the registry GET', async () => {
    listLinkEntityTypes.mockResolvedValue({
      data: { items: ['risk', 'document', 'incident'], total: 3 },
    })
    renderLinks()
    await waitFor(() => expect(listLinkEntityTypes).toHaveBeenCalled())
    await waitFor(() => {
      const select = screen.getByTestId('job-cell-links-entity-type') as HTMLSelectElement
      expect(Array.from(select.options).map((o) => o.value)).toEqual([
        'document',
        'incident',
        'risk',
      ])
    })
  })

  it('keeps a usable fallback list when the registry GET fails', async () => {
    listLinkEntityTypes.mockRejectedValue({ response: { status: 403 } })
    renderLinks()
    await waitFor(() => expect(listLinkEntityTypes).toHaveBeenCalled())
    const select = screen.getByTestId('job-cell-links-entity-type') as HTMLSelectElement
    expect(Array.from(select.options).map((o) => o.value)).toEqual([
      ...FALLBACK_APP_ENTITY_TYPES,
    ])
  })

  it('fetches the registry once per mount, not per render', async () => {
    listLinkEntityTypes.mockResolvedValue({ data: { items: ['document'], total: 1 } })
    const { rerender } = renderLinks()
    await waitFor(() => expect(listLinkEntityTypes).toHaveBeenCalledTimes(1))
    rerender(
      <MemoryRouter>
        <JobCellLinks
          jobTypeId={1}
          laneId={10}
          stepId={20}
          jobLifecycleEnabled
          jobCellLinksEnabled
          jobTypes={[jobType(1, 'Operational')]}
        />
      </MemoryRouter>,
    )
    await waitFor(() => expect(listLinkEntityTypes).toHaveBeenCalledTimes(1))
  })
})

describe('jobCellLinksHelpers W2 additions', () => {
  it('labels and detects the nest kind', () => {
    expect(jobCellLinkKindLabel('job_cycle')).toBe('Nested cycle')
    expect(isJobCycleNestLink({ kind: 'job_cycle' })).toBe(true)
    expect(isJobCycleNestLink({ kind: 'app' })).toBe(false)
  })

  it('normalises registry types, dropping job_type and deduping', () => {
    expect(normaliseAppEntityTypes(['Risk', 'risk', 'job_type', ' document '])).toEqual([
      'document',
      'risk',
    ])
  })

  it('falls back when the registry returns nothing usable', () => {
    expect(normaliseAppEntityTypes(null)).toEqual([...FALLBACK_APP_ENTITY_TYPES])
    expect(normaliseAppEntityTypes([])).toEqual([...FALLBACK_APP_ENTITY_TYPES])
    expect(normaliseAppEntityTypes(['job_type'])).toEqual([...FALLBACK_APP_ENTITY_TYPES])
  })
})
