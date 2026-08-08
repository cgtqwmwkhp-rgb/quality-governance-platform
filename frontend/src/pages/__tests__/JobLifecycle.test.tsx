/**
 * JobLifecycle page — flag-off + composer mount smoke (JL-2).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import JobLifecycle from '../JobLifecycle'
import { resetCoach } from '../../components/graph/graphCoachHelpers'

const apiGet = vi.fn()
const listJobTypes = vi.fn()
const listLanes = vi.fn()
const listSteps = vi.fn()
const listCells = vi.fn()
const putCellDocuments = vi.fn()
const createJobType = vi.fn()
const createLane = vi.fn()
const createStep = vi.fn()
const listBaselines = vi.fn()

const flagState: Record<string, boolean> = {
  job_lifecycle: false,
  document_graph_dnd_propose: false,
  graph_coach: false,
  entity_360: false,
  job_cell_links: false,
}

vi.mock('../../api/client', () => ({
  default: { get: (...args: unknown[]) => apiGet(...args) },
  jobLifecycleApi: {
    listJobTypes: (...args: unknown[]) => listJobTypes(...args),
    listLanes: (...args: unknown[]) => listLanes(...args),
    listSteps: (...args: unknown[]) => listSteps(...args),
    listCells: (...args: unknown[]) => listCells(...args),
    putCellDocuments: (...args: unknown[]) => putCellDocuments(...args),
    createJobType: (...args: unknown[]) => createJobType(...args),
    createLane: (...args: unknown[]) => createLane(...args),
    createStep: (...args: unknown[]) => createStep(...args),
    listBaselines: (...args: unknown[]) => listBaselines(...args),
  },
  getApiErrorMessage: (err: unknown) => (err as Error)?.message ?? 'error',
}))

vi.mock('../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (key: string) => Boolean(flagState[key]),
}))

vi.mock('../../components/jobLifecycle/JobCellLinks', () => ({
  default: () => <div data-testid="job-cell-links-stub" />,
}))

vi.mock('../../components/graph/Entity360Strip', () => ({
  Entity360Strip: ({ entityType, entityId }: { entityType: string; entityId: number }) => (
    <div data-testid="entity360-connections-strip">
      {entityType}:{entityId}
    </div>
  ),
}))

function renderAt(path = '/job-lifecycle') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/documents" element={<div data-testid="documents-fallback">Library</div>} />
        <Route path="/job-lifecycle" element={<JobLifecycle />} />
        <Route path="/job-lifecycle/steps/:stepId" element={<JobLifecycle />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('JobLifecycle flag gating', () => {
  beforeEach(() => {
    apiGet.mockReset()
    listJobTypes.mockReset()
    listLanes.mockReset()
    listSteps.mockReset()
    listCells.mockReset()
    putCellDocuments.mockReset()
    createJobType.mockReset()
    createLane.mockReset()
    createStep.mockReset()
    listBaselines.mockReset()
    listBaselines.mockResolvedValue({ data: { items: [], total: 0 } })
    flagState.job_lifecycle = false
    flagState.document_graph_dnd_propose = false
    flagState.graph_coach = false
    flagState.entity_360 = false
    flagState.job_cell_links = false
    resetCoach('job_lifecycle', localStorage)
  })

  it('redirects to library when job_lifecycle is off', () => {
    renderAt()
    expect(screen.getByTestId('documents-fallback')).toBeInTheDocument()
    expect(screen.queryByTestId('job-lifecycle-composer')).not.toBeInTheDocument()
    expect(listJobTypes).not.toHaveBeenCalled()
  })

  it('loads pack, mounts coach, and shows Entity360 for selected step when flag is on', async () => {
    flagState.job_lifecycle = true
    flagState.graph_coach = true
    flagState.entity_360 = true
    listJobTypes.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            tenant_id: 1,
            code: 'im',
            name: 'Incident Management',
            sort_order: 0,
            is_active: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:00:00Z',
          },
        ],
        total: 1,
      },
    })
    apiGet.mockResolvedValue({
      data: {
        items: [{ id: 7, title: 'IM Policy', reference_number: 'POL-7' }],
        pages: 1,
      },
    })
    listLanes.mockResolvedValue({
      data: {
        items: [
          {
            id: 10,
            tenant_id: 1,
            job_type_id: 1,
            code: 'qa',
            name: 'QA',
            sort_order: 0,
            is_active: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:00:00Z',
          },
        ],
        total: 1,
      },
    })
    listSteps.mockResolvedValue({
      data: {
        items: [
          {
            id: 20,
            tenant_id: 1,
            job_type_id: 1,
            code: 'review',
            name: 'Review',
            sort_order: 0,
            is_active: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:00:00Z',
          },
        ],
        total: 1,
      },
    })
    listCells.mockResolvedValue({
      data: {
        items: [
          {
            id: 100,
            tenant_id: 1,
            job_type_id: 1,
            lane_id: 10,
            step_id: 20,
            library_document_ids: [7],
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:00:00Z',
          },
        ],
        total: 1,
      },
    })

    renderAt()

    expect(await screen.findByTestId('job-lifecycle-composer')).toBeInTheDocument()
    expect(await screen.findByTestId('graph-coach-job_lifecycle')).toBeInTheDocument()
    await waitFor(() => {
      expect(listJobTypes).toHaveBeenCalled()
      expect(listLanes).toHaveBeenCalledWith(1)
      expect(listSteps).toHaveBeenCalledWith(1)
      expect(listCells).toHaveBeenCalledWith(1)
    })
    expect(screen.getByTestId('job-lifecycle-cell-10-20')).toBeInTheDocument()
    expect(screen.getByTestId('job-lifecycle-cell-doc-10-20-7')).toHaveTextContent('POL-7')
    expect(screen.getByTestId('entity360-connections-strip')).toHaveTextContent('job_step:20')
    expect(screen.getByTestId('job-lifecycle-view-matrix')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('job-lifecycle-cycle-picker')).toBeInTheDocument()
    expect(screen.getByTestId('job-lifecycle-resize-left')).toBeInTheDocument()
  })

  it('shows permission health banner when job types return 403', async () => {
    flagState.job_lifecycle = true
    listJobTypes.mockRejectedValue({ response: { status: 403 } })

    renderAt()

    expect(await screen.findByTestId('job-lifecycle-permission-health')).toBeInTheDocument()
    expect(screen.getByTestId('job-lifecycle-permission-health')).toHaveTextContent(/job:read/)
  })

  it('switches to phase view and deep-links a step', async () => {
    flagState.job_lifecycle = true
    listJobTypes.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            tenant_id: 1,
            code: 'im',
            name: 'IM',
            sort_order: 0,
            is_active: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:00:00Z',
          },
        ],
        total: 1,
      },
    })
    apiGet.mockResolvedValue({ data: { items: [], pages: 1 } })
    listLanes.mockResolvedValue({
      data: {
        items: [
          {
            id: 10,
            tenant_id: 1,
            job_type_id: 1,
            code: 'qa',
            name: 'QA',
            sort_order: 0,
            is_active: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:00:00Z',
          },
        ],
        total: 1,
      },
    })
    listSteps.mockResolvedValue({
      data: {
        items: [
          {
            id: 20,
            tenant_id: 1,
            job_type_id: 1,
            code: 'enquiry',
            name: 'Enquiry',
            sort_order: 0,
            is_active: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:00:00Z',
          },
          {
            id: 21,
            tenant_id: 1,
            job_type_id: 1,
            code: 'review',
            name: 'Review',
            sort_order: 1,
            is_active: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:00:00Z',
          },
        ],
        total: 2,
      },
    })
    listCells.mockResolvedValue({ data: { items: [], total: 0 } })

    renderAt('/job-lifecycle/steps/21')

    expect(await screen.findByTestId('job-lifecycle-composer')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByTestId('job-lifecycle-view-phase')).toHaveAttribute('aria-pressed', 'true')
    })
    expect(screen.getByTestId('job-lifecycle-col-21')).toBeInTheDocument()
    expect(screen.queryByTestId('job-lifecycle-col-20')).not.toBeInTheDocument()
  })

  it('attaches a document ref on cell drop via putCellDocuments', async () => {
    flagState.job_lifecycle = true
    flagState.document_graph_dnd_propose = true
    listJobTypes.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            tenant_id: 1,
            code: 'im',
            name: 'IM',
            sort_order: 0,
            is_active: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:00:00Z',
          },
        ],
        total: 1,
      },
    })
    apiGet.mockResolvedValue({
      data: {
        items: [{ id: 9, title: 'SOP', reference_number: 'SOP-9' }],
        pages: 1,
      },
    })
    listLanes.mockResolvedValue({
      data: {
        items: [
          {
            id: 10,
            tenant_id: 1,
            job_type_id: 1,
            code: 'qa',
            name: 'QA',
            sort_order: 0,
            is_active: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:00:00Z',
          },
        ],
        total: 1,
      },
    })
    listSteps.mockResolvedValue({
      data: {
        items: [
          {
            id: 20,
            tenant_id: 1,
            job_type_id: 1,
            code: 'review',
            name: 'Review',
            sort_order: 0,
            is_active: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:00:00Z',
          },
        ],
        total: 1,
      },
    })
    listCells.mockResolvedValue({ data: { items: [], total: 0 } })
    putCellDocuments.mockResolvedValue({
      data: {
        id: 100,
        tenant_id: 1,
        job_type_id: 1,
        lane_id: 10,
        step_id: 20,
        library_document_ids: [9],
        created_at: '2026-08-01T00:00:00Z',
        updated_at: '2026-08-01T00:00:00Z',
      },
    })

    renderAt()
    const cell = await screen.findByTestId('job-lifecycle-cell-10-20')

    const dataTransfer = {
      getData: (type: string) =>
        type === 'application/x-qgp-library-document' || type === 'text/plain'
          ? JSON.stringify({ documentId: 9, title: 'SOP' })
          : '',
      setData: vi.fn(),
      effectAllowed: 'copy',
      dropEffect: 'copy',
      types: ['application/x-qgp-library-document'],
    }

    fireEvent.drop(cell, { dataTransfer })

    await waitFor(() => {
      expect(putCellDocuments).toHaveBeenCalledWith(1, 10, 20, {
        library_document_ids: [9],
      })
    })
    expect(await screen.findByTestId('job-lifecycle-cell-doc-10-20-9')).toBeInTheDocument()
  })
})
