/**
 * JL-UX-W4 page behaviour — mandatory evidence, clone, Map/Trail, conflicts.
 *
 * The properties pinned hardest are the ones that would otherwise let the
 * composer overstate itself:
 *
 * 1. A refused edit reads as a *conflict* with a reload, never as "saved".
 * 2. Cloning says out loud that no cell and no document came with it.
 * 3. Map is not offered when `job_cell_links` is closed — an empty map would
 *    read as "nothing is nested" when the truth is "we were not allowed to look".
 * 4. Readiness is only requested when something is actually mandatory.
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
const updateLane = vi.fn()
const updateStep = vi.fn()
const cloneJobType = vi.fn()
const patchCellRequirement = vi.fn()
const listEvidenceReadiness = vi.fn()
const getCycleGraph = vi.fn()
const getAuditTrail = vi.fn()
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
    updateLane: (...args: unknown[]) => updateLane(...args),
    updateStep: (...args: unknown[]) => updateStep(...args),
    cloneJobType: (...args: unknown[]) => cloneJobType(...args),
    patchCellRequirement: (...args: unknown[]) => patchCellRequirement(...args),
    listEvidenceReadiness: (...args: unknown[]) => listEvidenceReadiness(...args),
    getCycleGraph: (...args: unknown[]) => getCycleGraph(...args),
    getAuditTrail: (...args: unknown[]) => getAuditTrail(...args),
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
const LATER = '2026-08-09T09:00:00Z'

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
  requires_evidence: false,
  library_document_ids: [7],
  links: [],
  created_at: NOW,
  updated_at: NOW,
}

const LIBRARY_PAGE = {
  items: [{ id: 7, title: 'Lifting plan', reference_number: 'PEL-7', status: 'approved' }],
  pages: 1,
  page: 1,
}

function readinessItem(overrides: Record<string, unknown> = {}) {
  return {
    cell_id: 100,
    lane_id: 10,
    step_id: 20,
    lane_name: 'QA',
    step_name: 'Prepare',
    requires_evidence: true,
    library_document_ids: [7],
    state: 'ready',
    reason: 'evidence_attached',
    evidence_count: 1,
    obsolete_count: 0,
    unresolved_count: 0,
    is_ready: true,
    ...overrides,
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

beforeEach(() => {
  for (const fn of [
    apiGet,
    listJobTypes,
    listLanes,
    listSteps,
    listCells,
    updateLane,
    updateStep,
    cloneJobType,
    patchCellRequirement,
    listEvidenceReadiness,
    getCycleGraph,
    getAuditTrail,
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
  listDocumentFreshness.mockResolvedValue({ data: { items: [], total: 0 } })
  listEvidenceReadiness.mockResolvedValue({
    data: { items: [], total: 0, job_type_id: 1, assure: false, summary: {} },
  })
  getCycleGraph.mockResolvedValue({
    data: { root_job_type_id: 1, depth: 2, truncated: false, nodes: [], edges: [] },
  })
  getAuditTrail.mockResolvedValue({
    data: {
      root_job_type_id: 1,
      assure: false,
      limit: 10,
      total_candidates: 0,
      truncated: false,
      paths: [],
      nodes: [],
      edges: [],
      summary: {},
    },
  })
})

describe('concurrency banner', () => {
  it('sends the read updated_at as the If-Match precondition', async () => {
    updateLane.mockResolvedValue({ data: { ...LANE, name: 'Quality' } })
    renderComposer()
    fireEvent.blur(await screen.findByTestId('job-lifecycle-lane-name-10'), {
      target: { value: 'Quality' },
    })

    await waitFor(() =>
      expect(updateLane).toHaveBeenCalledWith(10, { name: 'Quality' }, { ifMatch: NOW }),
    )
  })

  it('reads a 409 as a conflict with a reload, not as a saved edit', async () => {
    updateLane.mockRejectedValue({ response: { status: 409, data: { detail: 'stale' } } })
    renderComposer()
    fireEvent.blur(await screen.findByTestId('job-lifecycle-lane-name-10'), {
      target: { value: 'Quality' },
    })

    const banner = await screen.findByTestId('job-lifecycle-conflict-banner')
    expect(banner).toHaveTextContent('QA')
    expect(banner).toHaveTextContent('was not applied')
    expect(screen.queryByTestId('job-lifecycle-error')).not.toBeInTheDocument()
  })

  it('reloading from the banner re-reads the pack and clears it', async () => {
    updateStep.mockRejectedValue({ response: { status: 409 } })
    renderComposer()
    fireEvent.click(await screen.findByTestId('job-lifecycle-step-pdca-20'))
    await screen.findByTestId('job-lifecycle-conflict-banner')

    const before = listCells.mock.calls.length
    fireEvent.click(screen.getByTestId('job-lifecycle-conflict-reload'))

    await waitFor(() => expect(listCells.mock.calls.length).toBeGreaterThan(before))
    await waitFor(() =>
      expect(screen.queryByTestId('job-lifecycle-conflict-banner')).not.toBeInTheDocument(),
    )
  })

  it('keeps a non-409 failure in the ordinary error surface', async () => {
    updateLane.mockRejectedValue({ response: { status: 500, data: { detail: 'boom' } } })
    renderComposer()
    fireEvent.blur(await screen.findByTestId('job-lifecycle-lane-name-10'), {
      target: { value: 'Quality' },
    })

    expect(await screen.findByTestId('job-lifecycle-error')).toHaveTextContent('boom')
    expect(screen.queryByTestId('job-lifecycle-conflict-banner')).not.toBeInTheDocument()
  })
})

describe('clone job type pack', () => {
  it('clones axes only and says so, rather than implying the evidence came too', async () => {
    cloneJobType.mockResolvedValue({
      data: {
        job_type: { ...JOB_TYPE, id: 2, code: 'ops_v2', name: 'Ops v2' },
        source_job_type_id: 1,
        cloned_lane_count: 3,
        cloned_step_count: 4,
        cloned_cell_count: 0,
        cloned_document_count: 0,
      },
    })
    renderComposer()
    fireEvent.change(await screen.findByTestId('job-lifecycle-clone-name'), {
      target: { value: 'Ops v2' },
    })
    fireEvent.click(screen.getByTestId('job-lifecycle-clone-type'))

    await waitFor(() =>
      expect(cloneJobType).toHaveBeenCalledWith(1, { code: 'ops_v2', name: 'Ops v2' }),
    )
    const hint = await screen.findByTestId('job-lifecycle-drop-hint')
    expect(hint).toHaveTextContent('3 lane(s)')
    expect(hint).toHaveTextContent('4 step(s)')
    expect(hint).toHaveTextContent('Cells are empty')
  })

  it('will not clone without a name for the new pack', async () => {
    renderComposer()
    const button = await screen.findByTestId('job-lifecycle-clone-type')
    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(cloneJobType).not.toHaveBeenCalled()
  })
})

describe('mandatory evidence cells', () => {
  it('asks for no readiness while nothing in the pack is mandatory', async () => {
    renderComposer()
    await screen.findByTestId('job-lifecycle-cell-10-20')
    expect(listEvidenceReadiness).not.toHaveBeenCalled()
    expect(screen.queryByTestId('job-lifecycle-cell-readiness-10-20')).not.toBeInTheDocument()
  })

  it('marks a cell as owing evidence through the cell PATCH', async () => {
    patchCellRequirement.mockResolvedValue({ data: { ...CELL, requires_evidence: true } })
    listEvidenceReadiness.mockResolvedValue({
      data: {
        items: [readinessItem({ state: 'missing_evidence', is_ready: false })],
        total: 1,
        job_type_id: 1,
        assure: false,
        summary: { missing_evidence: 1 },
      },
    })
    renderComposer()
    const toggle = await screen.findByTestId('job-lifecycle-cell-requirement-10-20')
    expect(toggle).toHaveAttribute('data-requires-evidence', 'false')
    fireEvent.click(toggle)

    await waitFor(() =>
      expect(patchCellRequirement).toHaveBeenCalledWith(1, 10, 20, { requires_evidence: true }),
    )
    await waitFor(() =>
      expect(screen.getByTestId('job-lifecycle-cell-requirement-10-20')).toHaveAttribute(
        'data-requires-evidence',
        'true',
      ),
    )
  })

  it('shows the unsatisfied count and the derived cell verdict', async () => {
    listCells.mockResolvedValue({
      data: { items: [{ ...CELL, requires_evidence: true, library_document_ids: [] }], total: 1 },
    })
    listEvidenceReadiness.mockResolvedValue({
      data: {
        items: [
          readinessItem({
            state: 'missing_evidence',
            reason: 'no_evidence_attached',
            evidence_count: 0,
            library_document_ids: [],
            is_ready: false,
          }),
        ],
        total: 1,
        job_type_id: 1,
        assure: false,
        summary: { missing_evidence: 1 },
      },
    })
    renderComposer()

    const chip = await screen.findByTestId('job-lifecycle-cell-readiness-10-20')
    expect(chip).toHaveAttribute('data-readiness-state', 'missing_evidence')
    expect(await screen.findByTestId('job-lifecycle-readiness-summary')).toHaveTextContent(
      '1 mandatory-evidence cell(s) are not satisfied',
    )
  })

  it('assures readiness only once the operator asks for document status', async () => {
    listCells.mockResolvedValue({
      data: { items: [{ ...CELL, requires_evidence: true }], total: 1 },
    })
    listEvidenceReadiness.mockResolvedValue({
      data: {
        items: [readinessItem()],
        total: 1,
        job_type_id: 1,
        assure: false,
        summary: { ready: 1 },
      },
    })
    renderComposer()
    await waitFor(() => expect(listEvidenceReadiness).toHaveBeenCalledWith(1, false))

    fireEvent.click(screen.getByTestId('job-lifecycle-freshness-toggle'))
    await waitFor(() => expect(listEvidenceReadiness).toHaveBeenCalledWith(1, true))
  })

  it('says readiness is unknown rather than ready when the lookup fails', async () => {
    listCells.mockResolvedValue({
      data: { items: [{ ...CELL, requires_evidence: true }], total: 1 },
    })
    listEvidenceReadiness.mockRejectedValue({ response: { data: { detail: 'nope' } } })
    renderComposer()

    expect(await screen.findByTestId('job-lifecycle-readiness-error')).toHaveTextContent(
      'unknown rather than ready',
    )
    expect(screen.queryByTestId('job-lifecycle-readiness-summary')).not.toBeInTheDocument()
  })
})

describe('map and trail modes', () => {
  it('offers Map only while job_cell_links is open', async () => {
    renderComposer()
    expect(await screen.findByTestId('job-lifecycle-view-map')).toBeInTheDocument()
    expect(screen.getByTestId('job-lifecycle-view-trail')).toBeInTheDocument()
  })

  it('withholds Map when the links flag is closed, and keeps Trail', async () => {
    flagState.job_cell_links = false
    renderComposer()
    await screen.findByTestId('job-lifecycle-composer')

    expect(screen.queryByTestId('job-lifecycle-view-map')).not.toBeInTheDocument()
    expect(screen.getByTestId('job-lifecycle-view-trail')).toBeInTheDocument()
    expect(getCycleGraph).not.toHaveBeenCalled()
  })

  it('reads the map from the cycle-graph endpoint and replaces the swimlanes', async () => {
    getCycleGraph.mockResolvedValue({
      data: {
        root_job_type_id: 1,
        depth: 2,
        truncated: false,
        nodes: [
          { key: 'job_type:1', kind: 'job_type', ref_id: 1, label: 'Operational', href: null, detail: 'root' },
          { key: 'job_type:2', kind: 'job_type', ref_id: 2, label: 'Lifting', href: null, detail: null },
        ],
        edges: [
          {
            key: 'nests:job_type:1->job_type:2#100',
            kind: 'nests',
            source: 'job_type:1',
            target: 'job_type:2',
            label: 'Lifting ops',
            href: null,
            cell_id: 100,
            lane_id: 10,
            step_id: 20,
          },
        ],
      },
    })
    renderComposer()
    fireEvent.click(await screen.findByTestId('job-lifecycle-view-map'))

    expect(await screen.findByTestId('job-graph-panel-map')).toBeInTheDocument()
    await waitFor(() => expect(getCycleGraph).toHaveBeenCalledWith(1))
    expect(screen.queryByTestId('job-lifecycle-matrix')).not.toBeInTheDocument()
    expect(await screen.findByTestId('job-graph-node-job_type:2')).toHaveTextContent('Lifting')
    expect(screen.getByTestId('job-graph-edge-nests:job_type:1->job_type:2#100')).toHaveAttribute(
      'data-edge-kind',
      'nests',
    )
  })

  it('says an empty map means nothing is nested, not that the map is broken', async () => {
    renderComposer()
    fireEvent.click(await screen.findByTestId('job-lifecycle-view-map'))
    expect(await screen.findByTestId('job-graph-map-empty')).toHaveTextContent('no nested cycles')
  })

  it('walks a trail path and shows its readiness in the shared vocabulary', async () => {
    getAuditTrail.mockResolvedValue({
      data: {
        root_job_type_id: 1,
        assure: false,
        limit: 10,
        total_candidates: 3,
        truncated: true,
        paths: [
          {
            cell_id: 100,
            lane_id: 10,
            step_id: 20,
            lane_name: 'QA',
            step_name: 'Prepare',
            requires_evidence: true,
            library_document_ids: [7],
            node_keys: ['job_type:1', 'cell:100', 'document:7'],
            edge_keys: ['contains:job_type:1->cell:100'],
            readiness: {
              state: 'missing_evidence',
              reason: 'no_evidence_attached',
              evidence_count: 0,
              obsolete_count: 0,
              unresolved_count: 0,
              is_ready: false,
            },
          },
        ],
        nodes: [
          { key: 'job_type:1', kind: 'job_type', ref_id: 1, label: 'Operational', href: null, detail: 'root' },
          { key: 'cell:100', kind: 'cell', ref_id: 100, label: 'QA · Prepare', href: null, detail: null },
          { key: 'document:7', kind: 'document', ref_id: 7, label: 'PEL-7', href: '/documents/7', detail: null },
        ],
        edges: [],
        summary: { missing_evidence: 1 },
      },
    })
    renderComposer()
    fireEvent.click(await screen.findByTestId('job-lifecycle-view-trail'))

    expect(await screen.findByTestId('job-graph-trail-path-100')).toBeInTheDocument()
    expect(screen.getByTestId('job-graph-trail-readiness-100')).toHaveAttribute(
      'data-readiness-state',
      'missing_evidence',
    )
    expect(screen.getByTestId('job-graph-trail-sample')).toHaveTextContent('1 of 3 path(s)')
    expect(screen.getByTestId('job-graph-trail-truncated')).toHaveTextContent('sample')
  })

  it('follows the Freshness toggle when asking the trail to assure evidence', async () => {
    renderComposer()
    fireEvent.click(await screen.findByTestId('job-lifecycle-freshness-toggle'))
    fireEvent.click(screen.getByTestId('job-lifecycle-view-trail'))

    await waitFor(() => expect(getAuditTrail).toHaveBeenCalledWith(1, { assure: true }))
  })

  it('surfaces a failed graph read instead of drawing an empty pack', async () => {
    getCycleGraph.mockRejectedValue({ response: { data: { detail: 'no graph for you' } } })
    renderComposer()
    fireEvent.click(await screen.findByTestId('job-lifecycle-view-map'))

    expect(await screen.findByTestId('job-graph-error-map')).toHaveTextContent('no graph for you')
    expect(screen.queryByTestId('job-graph-map-empty')).not.toBeInTheDocument()
  })
})

describe('cell payloads from a pre-W4 server', () => {
  it('treats a cell with no requires_evidence field as optional', async () => {
    const legacyCell = { ...CELL }
    delete (legacyCell as { requires_evidence?: boolean }).requires_evidence
    listCells.mockResolvedValue({ data: { items: [legacyCell], total: 1 } })
    renderComposer()

    expect(await screen.findByTestId('job-lifecycle-cell-requirement-10-20')).toHaveAttribute(
      'data-requires-evidence',
      'false',
    )
    expect(listEvidenceReadiness).not.toHaveBeenCalled()
  })

  it('does not resend a stale token after the row comes back updated', async () => {
    updateLane
      .mockResolvedValueOnce({ data: { ...LANE, name: 'Quality', updated_at: LATER } })
      .mockResolvedValueOnce({ data: { ...LANE, name: 'Quality assurance', updated_at: LATER } })
    renderComposer()
    const input = await screen.findByTestId('job-lifecycle-lane-name-10')
    fireEvent.blur(input, { target: { value: 'Quality' } })
    await waitFor(() => expect(updateLane).toHaveBeenCalledTimes(1))

    fireEvent.blur(input, { target: { value: 'Quality assurance' } })
    await waitFor(() => expect(updateLane).toHaveBeenCalledTimes(2))
    expect(updateLane).toHaveBeenNthCalledWith(
      2,
      10,
      { name: 'Quality assurance' },
      { ifMatch: LATER },
    )
  })
})
