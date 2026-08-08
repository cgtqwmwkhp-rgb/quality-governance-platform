/**
 * JL-UX-W2 page behaviour — nest drill-in/out, PDCA colouring, axis reorder.
 *
 * The nest chip is asserted to be *derived*: the lane list renders a chip
 * purely because a cell in that lane carries a `job_cycle` link, with no lane
 * field involved. Reorder and rename go through the existing PATCH APIs.
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
const updateLane = vi.fn()
const updateStep = vi.fn()

const flagState: Record<string, boolean> = {
  job_lifecycle: true,
  document_graph_dnd_propose: false,
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
    createJobType: (...args: unknown[]) => createJobType(...args),
    createLane: (...args: unknown[]) => createLane(...args),
    createStep: (...args: unknown[]) => createStep(...args),
    updateLane: (...args: unknown[]) => updateLane(...args),
    updateStep: (...args: unknown[]) => updateStep(...args),
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
  Entity360Strip: () => <div data-testid="entity360-connections-strip" />,
}))

const NOW = '2026-08-08T00:00:00Z'

const OPERATIONAL = {
  id: 1,
  tenant_id: 1,
  code: 'ops',
  name: 'Operational',
  sort_order: 0,
  is_active: true,
  created_at: NOW,
  updated_at: NOW,
}

const ENGINEER = { ...OPERATIONAL, id: 2, code: 'eng', name: 'Engineer', sort_order: 1 }

const LANE_QA = {
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

const LANE_OPS = { ...LANE_QA, id: 11, code: 'ops_lane', name: 'Ops', sort_order: 1 }

const STEP_PLAN = {
  id: 20,
  tenant_id: 1,
  job_type_id: 1,
  code: 'prepare',
  name: 'Prepare',
  sort_order: 0,
  is_active: true,
  pdca_phase: 'plan' as const,
  created_at: NOW,
  updated_at: NOW,
}

const STEP_UNSET = {
  ...STEP_PLAN,
  id: 21,
  code: 'deliver',
  name: 'Deliver',
  sort_order: 1,
  pdca_phase: null,
}

const NEST_CELL = {
  id: 100,
  tenant_id: 1,
  job_type_id: 1,
  lane_id: 10,
  step_id: 20,
  library_document_ids: [],
  links: [
    {
      id: 500,
      tenant_id: 1,
      cell_id: 100,
      kind: 'job_cycle' as const,
      label: 'Engineer pack',
      target_job_type_id: 2,
      href: '/job-lifecycle/cycles/2',
      sort_order: 0,
      created_at: NOW,
      updated_at: NOW,
    },
  ],
  created_at: NOW,
  updated_at: NOW,
}

function renderAt(path = '/job-lifecycle') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/documents" element={<div data-testid="documents-fallback">Library</div>} />
        <Route path="/job-lifecycle" element={<JobLifecycle />} />
        <Route path="/job-lifecycle/steps/:stepId" element={<JobLifecycle />} />
        <Route path="/job-lifecycle/cycles/:jobTypeId" element={<JobLifecycle />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  for (const fn of [
    apiGet,
    listJobTypes,
    listLanes,
    listSteps,
    listCells,
    putCellDocuments,
    createJobType,
    createLane,
    createStep,
    updateLane,
    updateStep,
  ]) {
    fn.mockReset()
  }
  flagState.job_lifecycle = true
  flagState.job_cell_links = true
  flagState.graph_coach = false
  flagState.entity_360 = false
  flagState.document_graph_dnd_propose = false
  resetCoach('job_lifecycle', localStorage)
  localStorage.removeItem('job_lifecycle_view_mode')

  apiGet.mockResolvedValue({ data: { items: [], pages: 1 } })
  listJobTypes.mockResolvedValue({ data: { items: [OPERATIONAL, ENGINEER], total: 2 } })
  listLanes.mockResolvedValue({ data: { items: [LANE_QA, LANE_OPS], total: 2 } })
  listSteps.mockResolvedValue({ data: { items: [STEP_PLAN, STEP_UNSET], total: 2 } })
  listCells.mockResolvedValue({ data: { items: [NEST_CELL], total: 1 } })
})

describe('PDCA colouring', () => {
  it('colours step column headers by phase and marks an unset step as none', async () => {
    renderAt()
    expect(await screen.findByTestId('job-lifecycle-composer')).toBeInTheDocument()

    const planned = await screen.findByTestId('job-lifecycle-col-20')
    const unset = screen.getByTestId('job-lifecycle-col-21')
    expect(planned).toHaveAttribute('data-pdca-phase', 'plan')
    expect(unset).toHaveAttribute('data-pdca-phase', 'none')
    expect(planned.className).not.toEqual(unset.className)
    expect(planned).toHaveTextContent('Plan')
    expect(unset).toHaveTextContent('No phase')
  })

  it('does not colour lane headers — lanes have no Deming phase', async () => {
    renderAt()
    expect(await screen.findByTestId('job-lifecycle-composer')).toBeInTheDocument()
    const laneHeader = await screen.findByTestId('job-lifecycle-row-10')
    expect(laneHeader).not.toHaveAttribute('data-pdca-phase')
  })

  it('cycles a step phase through the existing step PATCH', async () => {
    updateStep.mockResolvedValue({ data: { ...STEP_PLAN, pdca_phase: 'do' } })
    renderAt()
    fireEvent.click(await screen.findByTestId('job-lifecycle-step-pdca-20'))

    await waitFor(() => {
      expect(updateStep).toHaveBeenCalledWith(20, { pdca_phase: 'do' })
    })
    await waitFor(() => {
      expect(screen.getByTestId('job-lifecycle-col-20')).toHaveAttribute('data-pdca-phase', 'do')
    })
  })

  it('clears the phase from act by sending an explicit null', async () => {
    listSteps.mockResolvedValue({
      data: { items: [{ ...STEP_PLAN, pdca_phase: 'act' }], total: 1 },
    })
    updateStep.mockResolvedValue({ data: { ...STEP_PLAN, pdca_phase: null } })
    renderAt()
    fireEvent.click(await screen.findByTestId('job-lifecycle-step-pdca-20'))

    await waitFor(() => {
      expect(updateStep).toHaveBeenCalledWith(20, { pdca_phase: null })
    })
  })
})

describe('derived lane nest chip and drill-in / drill-out', () => {
  it('derives the lane chip from a job_cycle cell link, not a lane field', async () => {
    renderAt()
    expect(await screen.findByTestId('job-lifecycle-composer')).toBeInTheDocument()

    // Lane 10 holds the nesting cell; lane 11 holds none.
    expect(await screen.findByTestId('job-lifecycle-lane-nest-chip-10-2')).toHaveTextContent(
      'Engineer',
    )
    expect(screen.queryByTestId('job-lifecycle-lane-nest-11')).not.toBeInTheDocument()
  })

  it('has no chip when the cell link list carries no nest link', async () => {
    listCells.mockResolvedValue({
      data: { items: [{ ...NEST_CELL, links: [] }], total: 1 },
    })
    renderAt()
    expect(await screen.findByTestId('job-lifecycle-composer')).toBeInTheDocument()
    expect(screen.queryByTestId('job-lifecycle-lane-nest-10')).not.toBeInTheDocument()
  })

  it('drills into the nested cycle from the lane chip and shows a breadcrumb', async () => {
    renderAt()
    expect(screen.queryByTestId('job-lifecycle-breadcrumb')).not.toBeInTheDocument()

    fireEvent.click(await screen.findByTestId('job-lifecycle-lane-nest-chip-10-2'))

    expect(await screen.findByTestId('job-lifecycle-breadcrumb')).toBeInTheDocument()
    expect(screen.getByTestId('job-lifecycle-breadcrumb-1')).toHaveTextContent('Operational')
    expect(screen.getByTestId('job-lifecycle-breadcrumb-current-2')).toHaveTextContent('Engineer')
    await waitFor(() => {
      expect(listLanes).toHaveBeenCalledWith(2)
      expect(listSteps).toHaveBeenCalledWith(2)
      expect(listCells).toHaveBeenCalledWith(2)
    })
  })

  it('drills back out via the breadcrumb ancestor', async () => {
    renderAt()
    fireEvent.click(await screen.findByTestId('job-lifecycle-lane-nest-chip-10-2'))
    fireEvent.click(await screen.findByTestId('job-lifecycle-breadcrumb-1'))

    await waitFor(() => {
      expect(screen.queryByTestId('job-lifecycle-breadcrumb')).not.toBeInTheDocument()
    })
    expect(await screen.findByTestId('job-lifecycle-lane-nest-chip-10-2')).toBeInTheDocument()
  })

  it('drills in from the nest chip inside the matrix cell', async () => {
    renderAt()
    fireEvent.click(await screen.findByTestId('job-lifecycle-cell-nest-10-20-500'))
    expect(await screen.findByTestId('job-lifecycle-breadcrumb-current-2')).toBeInTheDocument()
  })

  it('honours a deep link straight to a nested cycle', async () => {
    renderAt('/job-lifecycle/cycles/2')
    expect(await screen.findByTestId('job-lifecycle-composer')).toBeInTheDocument()
    await waitFor(() => {
      expect(listLanes).toHaveBeenCalledWith(2)
    })
    // Arriving cold there is no ancestor to drill back out to.
    expect(screen.queryByTestId('job-lifecycle-breadcrumb')).not.toBeInTheDocument()
  })
})

describe('axis rename and reorder use the existing PATCH APIs', () => {
  it('renames a lane on blur', async () => {
    updateLane.mockResolvedValue({ data: { ...LANE_QA, name: 'Quality' } })
    renderAt()
    const input = await screen.findByTestId('job-lifecycle-lane-name-10')
    fireEvent.blur(input, { target: { value: 'Quality' } })

    await waitFor(() => expect(updateLane).toHaveBeenCalledWith(10, { name: 'Quality' }))
  })

  it('does not PATCH when a rename leaves the name unchanged', async () => {
    renderAt()
    const input = await screen.findByTestId('job-lifecycle-lane-name-10')
    fireEvent.blur(input, { target: { value: 'QA' } })
    await waitFor(() => expect(listCells).toHaveBeenCalled())
    expect(updateLane).not.toHaveBeenCalled()
  })

  it('reorders a step down with dense sort_order writes', async () => {
    updateStep.mockImplementation((id: number, payload: { sort_order: number }) =>
      Promise.resolve({
        data: { ...(id === 20 ? STEP_PLAN : STEP_UNSET), sort_order: payload.sort_order },
      }),
    )
    renderAt()
    fireEvent.click(await screen.findByTestId('job-lifecycle-step-down-20'))

    await waitFor(() => expect(updateStep).toHaveBeenCalledTimes(2))
    expect(updateStep).toHaveBeenCalledWith(21, { sort_order: 0 })
    expect(updateStep).toHaveBeenCalledWith(20, { sort_order: 1 })
  })

  it('issues no PATCH when an axis is already at the end', async () => {
    renderAt()
    fireEvent.click(await screen.findByTestId('job-lifecycle-step-up-20'))
    fireEvent.click(await screen.findByTestId('job-lifecycle-lane-up-10'))
    await waitFor(() => expect(listCells).toHaveBeenCalled())
    expect(updateStep).not.toHaveBeenCalled()
    expect(updateLane).not.toHaveBeenCalled()
  })

  it('reorders a lane up', async () => {
    updateLane.mockImplementation((id: number, payload: { sort_order: number }) =>
      Promise.resolve({
        data: { ...(id === 10 ? LANE_QA : LANE_OPS), sort_order: payload.sort_order },
      }),
    )
    renderAt()
    fireEvent.click(await screen.findByTestId('job-lifecycle-lane-up-11'))

    await waitFor(() => expect(updateLane).toHaveBeenCalledTimes(2))
    expect(updateLane).toHaveBeenCalledWith(11, { sort_order: 0 })
    expect(updateLane).toHaveBeenCalledWith(10, { sort_order: 1 })
  })
})
