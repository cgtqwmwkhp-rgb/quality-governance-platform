import { describe, expect, it } from 'vitest'
import {
  attachDocumentRef,
  buildAxisCode,
  buildCellIndex,
  cellDocumentIds,
  cellKey,
  detachDocumentRef,
  emptyComposerCopy,
  isJobLifecycleViewMode,
  jobLifecycleViewModeLabel,
  libraryDocLabel,
  resolveDndCellAttach,
  resolveJobLifecycleViewMode,
  resolveSelectedJobTypeId,
  resolveSelectedStepId,
  resolveSwimlaneAxes,
  shouldFetchJobLifecycle,
  shouldShowJobLifecycle,
  sortAxesByOrder,
} from '../jobLifecycleHelpers'
import type { JobCell, JobLane, JobStep, JobType } from '../../api/jobLifecycleClient'

const lane = (id: number, name: string, sort_order = 0): JobLane => ({
  id,
  tenant_id: 1,
  job_type_id: 1,
  code: `l${id}`,
  name,
  sort_order,
  is_active: true,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
})

const step = (id: number, name: string, sort_order = 0): JobStep => ({
  id,
  tenant_id: 1,
  job_type_id: 1,
  code: `s${id}`,
  name,
  sort_order,
  is_active: true,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
})

const jobType = (id: number, name: string, sort_order = 0): JobType => ({
  id,
  tenant_id: 1,
  code: `jt${id}`,
  name,
  sort_order,
  is_active: true,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
})

describe('jobLifecycleHelpers', () => {
  it('gates visibility and fetch on job_lifecycle flag', () => {
    expect(shouldShowJobLifecycle(false)).toBe(false)
    expect(shouldFetchJobLifecycle(false)).toBe(false)
    expect(shouldShowJobLifecycle(true)).toBe(true)
    expect(shouldFetchJobLifecycle(true)).toBe(true)
  })

  it('resolves Matrix · Transpose · Phase view modes', () => {
    expect(isJobLifecycleViewMode('matrix')).toBe(true)
    expect(isJobLifecycleViewMode('phase')).toBe(true)
    expect(isJobLifecycleViewMode('vertical')).toBe(false)
    expect(resolveJobLifecycleViewMode('transpose')).toBe('transpose')
    expect(resolveJobLifecycleViewMode('nope')).toBe('matrix')
    expect(jobLifecycleViewModeLabel('phase')).toBe('Phase')
  })

  it('attaches and detaches library document refs without duplicates', () => {
    expect(attachDocumentRef([1, 2], 3)).toEqual([1, 2, 3])
    expect(attachDocumentRef([1, 2], 2)).toEqual([1, 2])
    expect(detachDocumentRef([1, 2, 3], 2)).toEqual([1, 3])
    expect(() => attachDocumentRef([], 0)).toThrow(/positive integer/)
  })

  it('resolves DnD cell attach to library_document_id[] only', () => {
    expect(
      resolveDndCellAttach({
        dragged: { documentId: 9, title: 'SOP' },
        existingIds: [1],
      }),
    ).toEqual({ ok: true, library_document_ids: [1, 9] })

    expect(resolveDndCellAttach({ dragged: null, existingIds: [] })).toEqual({
      ok: false,
      reason: 'Drop a library document onto the cell to attach a reference.',
    })
  })

  it('indexes cells and builds axis codes from names', () => {
    const cells: JobCell[] = [
      {
        id: 1,
        tenant_id: 1,
        job_type_id: 1,
        lane_id: 10,
        step_id: 20,
        library_document_ids: [7],
        created_at: '2026-08-01T00:00:00Z',
        updated_at: '2026-08-01T00:00:00Z',
      },
    ]
    const index = buildCellIndex(cells)
    expect(index.get(cellKey(10, 20))?.library_document_ids).toEqual([7])
    expect(cellDocumentIds(cells, 10, 20)).toEqual([7])
    expect(cellDocumentIds(cells, 99, 20)).toEqual([])
    expect(buildAxisCode('Incident Management')).toBe('incident_management')
    expect(buildAxisCode('  ')).toMatch(/^axis_/)
  })

  it('sorts axes and resolves selected type/step', () => {
    const types = [jobType(2, 'B', 1), jobType(1, 'A', 0)]
    expect(sortAxesByOrder(types).map((t) => t.id)).toEqual([1, 2])
    expect(resolveSelectedJobTypeId(2, types)).toBe(2)
    expect(resolveSelectedJobTypeId(99, types)).toBe(1)
    expect(resolveSelectedStepId(null, [step(5, 'Review', 0)])).toBe(5)
  })

  it('builds matrix / transpose / phase swimlane axes over the same cells', () => {
    const lanes = [lane(1, 'QA', 0), lane(2, 'Ops', 1)]
    const steps = [step(10, 'Enquiry', 0), step(11, 'Review', 1)]

    const matrix = resolveSwimlaneAxes({
      viewMode: 'matrix',
      lanes,
      steps,
      phaseStepId: null,
    })
    expect(matrix.rowAxis).toBe('lane')
    expect(matrix.columns.map((c) => c.id)).toEqual([10, 11])

    const transpose = resolveSwimlaneAxes({
      viewMode: 'transpose',
      lanes,
      steps,
      phaseStepId: null,
    })
    expect(transpose.rowAxis).toBe('step')
    expect(transpose.columns.map((c) => c.id)).toEqual([1, 2])

    const phase = resolveSwimlaneAxes({
      viewMode: 'phase',
      lanes,
      steps,
      phaseStepId: 11,
    })
    expect(phase.columns.map((c) => c.id)).toEqual([11])
    expect(phase.rows.map((r) => r.id)).toEqual([1, 2])
  })

  it('labels library docs and empty composer copy without department/org framing', () => {
    const map = new Map([
      [7, { id: 7, title: 'IM Policy', reference: 'POL-7' }],
    ])
    expect(libraryDocLabel(map, 7)).toBe('POL-7 · IM Policy')
    expect(libraryDocLabel(map, 9)).toBe('Document #9')
    expect(emptyComposerCopy(false)).toMatch(/not departments/)
    expect(emptyComposerCopy(true)).toMatch(/references/)
  })
})
