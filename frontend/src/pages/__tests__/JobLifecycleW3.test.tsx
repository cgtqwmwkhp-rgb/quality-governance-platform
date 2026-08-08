/**
 * JL-UX-W3 page behaviour — freshness toggle, tray/cell chips, obsolete block.
 *
 * Two properties are pinned harder than the happy path:
 *
 * 1. **Off means off.** With the toggle off the composer issues no freshness
 *    request and renders no chips, so an operator who does not want status
 *    noise does not pay for it either.
 * 2. **Obsolete is refused regardless of the toggle.** Enforcement is not a
 *    display preference — hiding the chip must not also disable the guard.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import JobLifecycle from '../JobLifecycle'
import { resetCoach } from '../../components/graph/graphCoachHelpers'
import { JOB_LIFECYCLE_FRESHNESS_STORAGE_KEY } from '../jobLifecycleHelpers'

const apiGet = vi.fn()
const listJobTypes = vi.fn()
const listLanes = vi.fn()
const listSteps = vi.fn()
const listCells = vi.fn()
const putCellDocuments = vi.fn()
const listDocumentFreshness = vi.fn()
const listBaselines = vi.fn()

const flagState: Record<string, boolean> = {
  job_lifecycle: true,
  document_graph_dnd_propose: true,
  graph_coach: false,
  entity_360: false,
  job_cell_links: true,
}

vi.mock('../../api/client', () => ({
  default: { get: (...args: unknown[]) => apiGet(...args) },
  jobLifecycleApi: {
    listJobTypes: (...args: unknown[]) => listJobTypes(...args),
    listLanes: (...args: unknown[]) => listLanes(...args),
    listSteps: (...args: unknown[]) => listSteps(...args),
    listCells: (...args: unknown[]) => listCells(...args),
    putCellDocuments: (...args: unknown[]) => putCellDocuments(...args),
    listDocumentFreshness: (...args: unknown[]) => listDocumentFreshness(...args),
    listBaselines: (...args: unknown[]) => listBaselines(...args),
  },
  getApiErrorMessage: (err: unknown) =>
    (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
    (err as Error)?.message ??
    'error',
}))

vi.mock('../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (key: string) => Boolean(flagState[key]),
}))

vi.mock('../../components/jobLifecycle/JobCellLinks', () => ({
  default: () => <div data-testid="job-cell-links-stub" />,
}))

vi.mock('../../components/graph/Entity360Strip', () => ({
  Entity360Strip: () => <div data-testid="entity360-connections-strip" />,
}))

const NOW = '2026-08-08T00:00:00Z'

const JOB_TYPE = {
  id: 1,
  tenant_id: 1,
  code: 'ops',
  name: 'Operational',
  sort_order: 0,
  is_active: true,
  created_at: NOW,
  updated_at: NOW,
}

const LANE = {
  id: 10,
  tenant_id: 1,
  job_type_id: 1,
  code: 'qa',
  name: 'QA',
  sort_order: 0,
  is_active: true,
  created_at: NOW,
  updated_at: NOW,
}

const STEP = {
  id: 20,
  tenant_id: 1,
  job_type_id: 1,
  code: 'prepare',
  name: 'Prepare',
  sort_order: 0,
  is_active: true,
  pdca_phase: null,
  created_at: NOW,
  updated_at: NOW,
}

const CELL = {
  id: 100,
  tenant_id: 1,
  job_type_id: 1,
  lane_id: 10,
  step_id: 20,
  library_document_ids: [7],
  links: [],
  created_at: NOW,
  updated_at: NOW,
}

const LIBRARY_PAGE = {
  items: [
    { id: 7, title: 'Lifting plan', reference_number: 'PEL-7', status: 'approved', review_date: null },
    { id: 8, title: 'Old method statement', reference_number: 'PEL-8', status: 'obsolete', review_date: null },
  ],
  pages: 1,
  page: 1,
}

function freshness(id: number, state: string, extra: Record<string, unknown> = {}) {
  return {
    library_document_id: id,
    found: true,
    title: `Doc ${id}`,
    reference: `PEL-${id}`,
    library_status: 'approved',
    controlled_status: null,
    state,
    reason: state === 'unknown' ? 'no_review_date' : 'review_current',
    review_date: null,
    is_obsolete: state === 'obsolete',
    ...extra,
  }
}

function renderComposer() {
  return render(
    <MemoryRouter initialEntries={['/job-lifecycle']}>
      <Routes>
        <Route path="/documents" element={<div data-testid="documents-fallback">Library</div>} />
        <Route path="/job-lifecycle" element={<JobLifecycle />} />
      </Routes>
    </MemoryRouter>,
  )
}

/** A DataTransfer stub carrying the shared library-document drag payload. */
function dragData(documentId: number) {
  const payload = JSON.stringify({ documentId, title: `Doc ${documentId}` })
  return {
    dataTransfer: {
      types: ['application/x-qgp-library-document'],
      getData: (type: string) =>
        type === 'application/x-qgp-library-document' ? payload : '',
      setData: vi.fn(),
      dropEffect: 'copy',
      effectAllowed: 'copy',
    },
  }
}

beforeEach(() => {
  for (const fn of [
    apiGet,
    listJobTypes,
    listLanes,
    listSteps,
    listCells,
    putCellDocuments,
    listDocumentFreshness,
    listBaselines,
  ]) {
    fn.mockReset()
  }
  flagState.job_lifecycle = true
  flagState.job_cell_links = true
  flagState.document_graph_dnd_propose = true
  resetCoach('job_lifecycle', localStorage)
  localStorage.removeItem('job_lifecycle_view_mode')
  localStorage.removeItem(JOB_LIFECYCLE_FRESHNESS_STORAGE_KEY)

  apiGet.mockResolvedValue({ data: LIBRARY_PAGE })
  listJobTypes.mockResolvedValue({ data: { items: [JOB_TYPE], total: 1 } })
  listLanes.mockResolvedValue({ data: { items: [LANE], total: 1 } })
  listSteps.mockResolvedValue({ data: { items: [STEP], total: 1 } })
  listBaselines.mockResolvedValue({ data: { items: [], total: 0 } })
  listCells.mockResolvedValue({ data: { items: [CELL], total: 1 } })
  listDocumentFreshness.mockResolvedValue({
    data: { items: [freshness(7, 'overdue'), freshness(8, 'obsolete')], total: 2 },
  })
})

describe('freshness toggle', () => {
  it('starts off, renders no chips, and asks for no status', async () => {
    renderComposer()
    expect(await screen.findByTestId('job-lifecycle-composer')).toBeInTheDocument()
    await screen.findByTestId('job-lifecycle-library-doc-7')

    expect(screen.getByTestId('job-lifecycle-freshness-toggle')).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(screen.queryByTestId('job-lifecycle-library-freshness-7')).not.toBeInTheDocument()
    expect(screen.queryByTestId('job-lifecycle-cell-doc-freshness-10-20-7')).not.toBeInTheDocument()
    expect(listDocumentFreshness).not.toHaveBeenCalled()
  })

  it('turning it on loads status onto tray and cell chips', async () => {
    renderComposer()
    fireEvent.click(await screen.findByTestId('job-lifecycle-freshness-toggle'))

    const cellChip = await screen.findByTestId('job-lifecycle-cell-doc-freshness-10-20-7')
    expect(cellChip).toHaveAttribute('data-freshness-state', 'overdue')
    expect(cellChip).toHaveTextContent('Overdue')

    const trayChip = await screen.findByTestId('job-lifecycle-library-freshness-8')
    expect(trayChip).toHaveAttribute('data-freshness-state', 'obsolete')
  })

  it('asks for the attached refs as well as the tray page', async () => {
    renderComposer()
    fireEvent.click(await screen.findByTestId('job-lifecycle-freshness-toggle'))

    await waitFor(() => expect(listDocumentFreshness).toHaveBeenCalledTimes(1))
    const requested = listDocumentFreshness.mock.calls[0][0] as number[]
    expect(requested).toContain(7)
    expect(requested).toContain(8)
  })

  it('persists the choice and restores it on the next mount', async () => {
    const first = renderComposer()
    fireEvent.click(await screen.findByTestId('job-lifecycle-freshness-toggle'))
    await waitFor(() =>
      expect(localStorage.getItem(JOB_LIFECYCLE_FRESHNESS_STORAGE_KEY)).toBe('on'),
    )
    first.unmount()

    renderComposer()
    expect(await screen.findByTestId('job-lifecycle-freshness-toggle')).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(await screen.findByTestId('job-lifecycle-cell-doc-freshness-10-20-7')).toBeInTheDocument()
  })

  it('does not re-request status for ids it already holds', async () => {
    renderComposer()
    const toggle = await screen.findByTestId('job-lifecycle-freshness-toggle')
    fireEvent.click(toggle)
    await waitFor(() => expect(listDocumentFreshness).toHaveBeenCalledTimes(1))

    fireEvent.click(toggle)
    fireEvent.click(toggle)
    await screen.findByTestId('job-lifecycle-cell-doc-freshness-10-20-7')
    expect(listDocumentFreshness).toHaveBeenCalledTimes(1)
  })

  it('shows a document with no verdict as unknown, never as current', async () => {
    listDocumentFreshness.mockResolvedValue({ data: { items: [freshness(7, 'current')], total: 1 } })
    renderComposer()
    fireEvent.click(await screen.findByTestId('job-lifecycle-freshness-toggle'))

    // Document 8 was requested but came back in no verdict.
    const trayChip = await screen.findByTestId('job-lifecycle-library-freshness-8')
    expect(trayChip).toHaveAttribute('data-freshness-state', 'unknown')
    expect(trayChip).toHaveTextContent('Unknown')
  })

  it('says so when the status lookup fails rather than showing everything as fine', async () => {
    listDocumentFreshness.mockRejectedValue(new Error('freshness unavailable'))
    renderComposer()
    fireEvent.click(await screen.findByTestId('job-lifecycle-freshness-toggle'))

    expect(await screen.findByTestId('job-lifecycle-freshness-error')).toHaveTextContent(
      /unknown rather than current/i,
    )
    expect(
      await screen.findByTestId('job-lifecycle-cell-doc-freshness-10-20-7'),
    ).toHaveAttribute('data-freshness-state', 'unknown')
  })
})

describe('obsolete enforcement on attach', () => {
  it('refuses a drop of an obsolete document and never calls the API', async () => {
    renderComposer()
    fireEvent.click(await screen.findByTestId('job-lifecycle-freshness-toggle'))
    await screen.findByTestId('job-lifecycle-library-freshness-8')

    fireEvent.drop(screen.getByTestId('job-lifecycle-cell-10-20'), dragData(8))

    expect(await screen.findByTestId('job-lifecycle-drop-hint')).toHaveTextContent(
      /Obsolete documents cannot be attached/,
    )
    expect(putCellDocuments).not.toHaveBeenCalled()
  })

  it('refuses it with freshness off too — the guard is not a display setting', async () => {
    renderComposer()
    await screen.findByTestId('job-lifecycle-library-doc-8')
    expect(listDocumentFreshness).not.toHaveBeenCalled()

    fireEvent.drop(screen.getByTestId('job-lifecycle-cell-10-20'), dragData(8))

    // Falls back to the raw status carried through tray ingest.
    expect(await screen.findByTestId('job-lifecycle-drop-hint')).toHaveTextContent(
      /Obsolete documents cannot be attached/,
    )
    expect(putCellDocuments).not.toHaveBeenCalled()
  })

  it('still attaches a document that is merely overdue', async () => {
    putCellDocuments.mockResolvedValue({
      data: { ...CELL, library_document_ids: [7, 9] },
    })
    listCells.mockResolvedValue({
      data: { items: [{ ...CELL, library_document_ids: [] }], total: 1 },
    })
    listDocumentFreshness.mockResolvedValue({
      data: { items: [freshness(7, 'overdue')], total: 1 },
    })
    renderComposer()
    fireEvent.click(await screen.findByTestId('job-lifecycle-freshness-toggle'))
    await screen.findByTestId('job-lifecycle-library-freshness-7')

    fireEvent.drop(screen.getByTestId('job-lifecycle-cell-10-20'), dragData(7))

    await waitFor(() =>
      expect(putCellDocuments).toHaveBeenCalledWith(1, 10, 20, { library_document_ids: [7] }),
    )
  })

  it('surfaces the server refusal when the client had no status to pre-flight on', async () => {
    listCells.mockResolvedValue({
      data: { items: [{ ...CELL, library_document_ids: [] }], total: 1 },
    })
    apiGet.mockResolvedValue({
      data: { items: [{ id: 9, title: 'Unlisted', reference_number: null }], pages: 1 },
    })
    putCellDocuments.mockRejectedValue({
      response: { data: { detail: 'Obsolete documents cannot be attached — 9 (obsolete)' } },
    })
    renderComposer()
    await screen.findByTestId('job-lifecycle-library-doc-9')

    fireEvent.drop(screen.getByTestId('job-lifecycle-cell-10-20'), dragData(9))

    expect(await screen.findByTestId('job-lifecycle-error')).toHaveTextContent(
      /Obsolete documents cannot be attached/,
    )
  })
})

describe('audit lapse cue in a cell', () => {
  it('renders the server verdict on an audit_outcome chip', async () => {
    listCells.mockResolvedValue({
      data: {
        items: [
          {
            ...CELL,
            links: [
              {
                id: 500,
                tenant_id: 1,
                cell_id: 100,
                kind: 'audit_outcome' as const,
                label: 'Finding 12',
                audit_run_id: 5,
                audit_finding_id: 12,
                href: '/audits/runs/5/findings/12',
                audit_lapse: {
                  state: 'lapsed' as const,
                  reason: 'cadence_overdue',
                  next_due_at: NOW,
                  frequency: 'annually',
                  frequency_days: 365,
                },
                sort_order: 0,
                created_at: NOW,
                updated_at: NOW,
              },
            ],
          },
        ],
        total: 1,
      },
    })
    renderComposer()
    const chip = await screen.findByTestId('job-lifecycle-cell-lapse-10-20-500')
    expect(chip).toHaveAttribute('data-lapse-state', 'lapsed')
    expect(chip).toHaveTextContent('Lapsed')
  })

  it('reads as unknown when the server sent no lapse, not as in date', async () => {
    listCells.mockResolvedValue({
      data: {
        items: [
          {
            ...CELL,
            links: [
              {
                id: 501,
                tenant_id: 1,
                cell_id: 100,
                kind: 'audit_outcome' as const,
                label: 'Finding 13',
                audit_run_id: 6,
                audit_finding_id: 13,
                href: '/audits/runs/6/findings/13',
                sort_order: 0,
                created_at: NOW,
                updated_at: NOW,
              },
            ],
          },
        ],
        total: 1,
      },
    })
    renderComposer()
    const chip = await screen.findByTestId('job-lifecycle-cell-lapse-10-20-501')
    expect(chip).toHaveAttribute('data-lapse-state', 'unknown')
    expect(chip).toHaveTextContent('Unknown')
  })
})
