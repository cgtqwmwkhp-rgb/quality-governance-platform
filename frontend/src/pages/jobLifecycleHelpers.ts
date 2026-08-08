/**
 * Job Lifecycle swimlane composer helpers (JL-2 / ADR-0022).
 *
 * View modes Matrix · Transpose · Phase are layout only — same cells, same
 * library_document_id refs. DnD attaches IDs never document bodies.
 */
import type { LibraryDocumentDragPayload } from '../components/graph/documentGraphDndHelpers'
import type { JobCell, JobLane, JobStep, JobType } from '../api/jobLifecycleClient'

export type JobLifecycleViewMode = 'matrix' | 'transpose' | 'phase'

export const JOB_LIFECYCLE_VIEW_MODES: readonly JobLifecycleViewMode[] = [
  'matrix',
  'transpose',
  'phase',
] as const

export const DEFAULT_JOB_LIFECYCLE_VIEW_MODE: JobLifecycleViewMode = 'matrix'

export const JOB_LIFECYCLE_VIEW_STORAGE_KEY = 'job_lifecycle_view_mode'

export interface JobLifecycleLibraryDoc {
  id: number
  title: string
  reference?: string | null
}

export type CellAttachResult =
  | { ok: true; library_document_ids: number[] }
  | { ok: false; reason: string }

export function shouldShowJobLifecycle(jobLifecycleEnabled: boolean): boolean {
  return Boolean(jobLifecycleEnabled)
}

export function shouldFetchJobLifecycle(jobLifecycleEnabled: boolean): boolean {
  return Boolean(jobLifecycleEnabled)
}

export function isJobLifecycleViewMode(value: unknown): value is JobLifecycleViewMode {
  return value === 'matrix' || value === 'transpose' || value === 'phase'
}

export function resolveJobLifecycleViewMode(
  preferred: unknown,
  fallback: JobLifecycleViewMode = DEFAULT_JOB_LIFECYCLE_VIEW_MODE,
): JobLifecycleViewMode {
  return isJobLifecycleViewMode(preferred) ? preferred : fallback
}

export function jobLifecycleViewModeLabel(mode: JobLifecycleViewMode): string {
  if (mode === 'matrix') return 'Matrix'
  if (mode === 'transpose') return 'Transpose'
  return 'Phase'
}

export function parseStoredJobLifecycleViewMode(
  raw: string | null | undefined,
): JobLifecycleViewMode | null {
  return isJobLifecycleViewMode(raw) ? raw : null
}

export function readStoredJobLifecycleViewMode(
  storage: Pick<Storage, 'getItem'> | null | undefined = typeof localStorage !== 'undefined'
    ? localStorage
    : null,
): JobLifecycleViewMode | null {
  if (!storage) return null
  try {
    return parseStoredJobLifecycleViewMode(storage.getItem(JOB_LIFECYCLE_VIEW_STORAGE_KEY))
  } catch {
    return null
  }
}

export function writeStoredJobLifecycleViewMode(
  mode: JobLifecycleViewMode,
  storage: Pick<Storage, 'setItem'> | null | undefined = typeof localStorage !== 'undefined'
    ? localStorage
    : null,
): void {
  if (!storage) return
  try {
    storage.setItem(JOB_LIFECYCLE_VIEW_STORAGE_KEY, mode)
  } catch {
    // Storage may be unavailable — ignore.
  }
}

export function sortAxesByOrder<T extends { sort_order: number; name: string; id: number }>(
  items: readonly T[],
): T[] {
  return items.slice().sort((a, b) => {
    if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order
    const byName = a.name.localeCompare(b.name)
    if (byName !== 0) return byName
    return a.id - b.id
  })
}

export function cellKey(laneId: number, stepId: number): string {
  return `${laneId}:${stepId}`
}

export function findCell(
  cells: readonly JobCell[],
  laneId: number,
  stepId: number,
): JobCell | null {
  return cells.find((cell) => cell.lane_id === laneId && cell.step_id === stepId) ?? null
}

export function cellDocumentIds(
  cells: readonly JobCell[],
  laneId: number,
  stepId: number,
): number[] {
  return findCell(cells, laneId, stepId)?.library_document_ids ?? []
}

/** Append a library document ID — refs only, no body copy, no duplicates. */
export function attachDocumentRef(existingIds: readonly number[], documentId: number): number[] {
  if (!Number.isFinite(documentId) || documentId <= 0) {
    throw new Error('library_document_id must be a positive integer')
  }
  if (existingIds.includes(documentId)) return existingIds.slice()
  return [...existingIds, documentId]
}

export function detachDocumentRef(existingIds: readonly number[], documentId: number): number[] {
  return existingIds.filter((id) => id !== documentId)
}

export function resolveDndCellAttach(input: {
  dragged: LibraryDocumentDragPayload | null
  existingIds: readonly number[]
}): CellAttachResult {
  if (!input.dragged) {
    return { ok: false, reason: 'Drop a library document onto the cell to attach a reference.' }
  }
  try {
    return {
      ok: true,
      library_document_ids: attachDocumentRef(input.existingIds, input.dragged.documentId),
    }
  } catch (err) {
    return {
      ok: false,
      reason: err instanceof Error ? err.message : 'Could not attach document reference',
    }
  }
}

/** Stable JL axis code from a display name (not an org/department identity). */
export function buildAxisCode(name: string, fallbackPrefix = 'axis'): string {
  const slug = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 64)
  if (slug) return slug
  const stamp = Date.now().toString(36)
  return `${fallbackPrefix}_${stamp}`.slice(0, 64)
}

export function resolveSelectedJobTypeId(
  preferred: number | null,
  jobTypes: readonly JobType[],
): number | null {
  if (preferred != null && jobTypes.some((jt) => jt.id === preferred)) return preferred
  const active = sortAxesByOrder(jobTypes.filter((jt) => jt.is_active))
  if (active[0]) return active[0].id
  const any = sortAxesByOrder(jobTypes)
  return any[0]?.id ?? null
}

export function resolveSelectedStepId(
  preferred: number | null,
  steps: readonly JobStep[],
): number | null {
  if (preferred != null && steps.some((step) => step.id === preferred)) return preferred
  const ordered = sortAxesByOrder(steps.filter((step) => step.is_active))
  if (ordered[0]) return ordered[0].id
  const any = sortAxesByOrder(steps)
  return any[0]?.id ?? null
}

export function libraryDocLabel(
  docsById: ReadonlyMap<number, JobLifecycleLibraryDoc>,
  documentId: number,
): string {
  const doc = docsById.get(documentId)
  if (!doc) return `Document #${documentId}`
  if (doc.reference) return `${doc.reference} · ${doc.title}`
  return doc.title || `Document #${documentId}`
}

export function buildCellIndex(cells: readonly JobCell[]): Map<string, JobCell> {
  const map = new Map<string, JobCell>()
  for (const cell of cells) {
    map.set(cellKey(cell.lane_id, cell.step_id), cell)
  }
  return map
}

export function matrixColumns(viewMode: JobLifecycleViewMode, steps: readonly JobStep[]): JobStep[] {
  if (viewMode === 'transpose') return []
  return sortAxesByOrder(steps)
}

export function matrixRows(viewMode: JobLifecycleViewMode, lanes: readonly JobLane[]): JobLane[] {
  if (viewMode === 'transpose') return []
  return sortAxesByOrder(lanes)
}

/** Row / column axes for the active view (phase collapses to one step column). */
export function resolveSwimlaneAxes(input: {
  viewMode: JobLifecycleViewMode
  lanes: readonly JobLane[]
  steps: readonly JobStep[]
  phaseStepId: number | null
}): {
  rowAxis: 'lane' | 'step'
  columnAxis: 'lane' | 'step'
  rows: Array<JobLane | JobStep>
  columns: Array<JobLane | JobStep>
} {
  const lanes = sortAxesByOrder(input.lanes)
  const steps = sortAxesByOrder(input.steps)

  if (input.viewMode === 'transpose') {
    return {
      rowAxis: 'step',
      columnAxis: 'lane',
      rows: steps,
      columns: lanes,
    }
  }

  if (input.viewMode === 'phase') {
    const phaseStep =
      (input.phaseStepId != null ? steps.find((s) => s.id === input.phaseStepId) : null) ??
      steps[0] ??
      null
    return {
      rowAxis: 'lane',
      columnAxis: 'step',
      rows: lanes,
      columns: phaseStep ? [phaseStep] : [],
    }
  }

  return {
    rowAxis: 'lane',
    columnAxis: 'step',
    rows: lanes,
    columns: steps,
  }
}

export function emptyComposerCopy(hasJobTypes: boolean): string {
  if (!hasJobTypes) {
    return 'Create a job type to start composing swimlanes. Lanes and steps are process axes — not departments.'
  }
  return 'Add lanes and steps for this job type, then drag library documents onto cells to attach references.'
}
