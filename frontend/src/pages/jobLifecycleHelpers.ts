/**
 * Job Lifecycle swimlane composer helpers (JL-2 / ADR-0022).
 *
 * View modes Matrix · Transpose · Phase are layout only — same cells, same
 * library_document_id refs. DnD attaches IDs never document bodies.
 */
import type { LibraryDocumentDragPayload } from '../components/graph/documentGraphDndHelpers'
import type {
  JobAuditLapseState,
  JobCell,
  JobDocumentFreshness,
  JobDocumentFreshnessState,
  JobLane,
  JobStep,
  JobStepPdcaPhase,
  JobType,
} from '../api/jobLifecycleClient'

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
  /**
   * Raw Library status as the list API returned it. Carried through tray
   * ingest rather than discarded: with freshness ON it is what the chip falls
   * back to if the authoritative lookup has not answered yet.
   */
  status?: string | null
  review_date?: string | null
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
    return 'Create a job cycle to start composing swimlanes. Lanes and steps are process axes — not departments.'
  }
  return 'Add lanes and steps for this job cycle, then drag library documents onto cells to attach references.'
}

/** JL-UX-W1 — composer column widths (px) persisted locally. */
export const JOB_LIFECYCLE_PANEL_STORAGE_KEY = 'job_lifecycle_panel_widths'

export type JobLifecyclePanelWidths = {
  left: number
  right: number
}

export const DEFAULT_JOB_LIFECYCLE_PANEL_WIDTHS: JobLifecyclePanelWidths = {
  left: 240,
  right: 260,
}

export const JOB_LIFECYCLE_PANEL_BOUNDS = {
  leftMin: 180,
  leftMax: 420,
  rightMin: 200,
  rightMax: 480,
} as const

export function clampJobLifecyclePanelWidth(
  value: number,
  min: number,
  max: number,
): number {
  if (!Number.isFinite(value)) return min
  return Math.min(max, Math.max(min, Math.round(value)))
}

export function resolveJobLifecyclePanelWidths(
  preferred: Partial<JobLifecyclePanelWidths> | null | undefined,
  fallback: JobLifecyclePanelWidths = DEFAULT_JOB_LIFECYCLE_PANEL_WIDTHS,
): JobLifecyclePanelWidths {
  return {
    left: clampJobLifecyclePanelWidth(
      preferred?.left ?? fallback.left,
      JOB_LIFECYCLE_PANEL_BOUNDS.leftMin,
      JOB_LIFECYCLE_PANEL_BOUNDS.leftMax,
    ),
    right: clampJobLifecyclePanelWidth(
      preferred?.right ?? fallback.right,
      JOB_LIFECYCLE_PANEL_BOUNDS.rightMin,
      JOB_LIFECYCLE_PANEL_BOUNDS.rightMax,
    ),
  }
}

export function readStoredJobLifecyclePanelWidths(
  storage: Pick<Storage, 'getItem'> | null | undefined = typeof localStorage !== 'undefined'
    ? localStorage
    : null,
): JobLifecyclePanelWidths | null {
  if (!storage) return null
  try {
    const raw = storage.getItem(JOB_LIFECYCLE_PANEL_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<JobLifecyclePanelWidths>
    return resolveJobLifecyclePanelWidths(parsed)
  } catch {
    return null
  }
}

export function writeStoredJobLifecyclePanelWidths(
  widths: JobLifecyclePanelWidths,
  storage: Pick<Storage, 'setItem'> | null | undefined = typeof localStorage !== 'undefined'
    ? localStorage
    : null,
): void {
  if (!storage) return
  try {
    storage.setItem(
      JOB_LIFECYCLE_PANEL_STORAGE_KEY,
      JSON.stringify(resolveJobLifecyclePanelWidths(widths)),
    )
  } catch {
    // Storage may be unavailable — ignore.
  }
}

/** Permission-health (#10): flags ON does not mean grants exist. */
export function isForbiddenApiError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false
  const maybe = error as { response?: { status?: number }; status_code?: number }
  if (maybe.response?.status === 403) return true
  if (maybe.status_code === 403) return true
  return false
}

export const JOB_LIFECYCLE_PERMISSION_HEALTH_COPY =
  'Job Lifecycle flags are on, but this account is missing job:read / job:author (or is_superuser). Ask an admin to grant those permissions — flags alone do not unlock authoring.'

/* -------------------------------------------------------------------------- */
/* JL-UX-W2 — PDCA phase colouring                                            */
/* -------------------------------------------------------------------------- */

export const JOB_STEP_PDCA_PHASES: readonly JobStepPdcaPhase[] = [
  'plan',
  'do',
  'check',
  'act',
] as const

export function isJobStepPdcaPhase(value: unknown): value is JobStepPdcaPhase {
  return value === 'plan' || value === 'do' || value === 'check' || value === 'act'
}

/** Tolerant reader: an unknown or absent phase is `null`, never a fabricated default. */
export function resolvePdcaPhase(value: unknown): JobStepPdcaPhase | null {
  if (typeof value !== 'string') return null
  const cleaned = value.trim().toLowerCase()
  return isJobStepPdcaPhase(cleaned) ? cleaned : null
}

export function pdcaPhaseLabel(phase: JobStepPdcaPhase | null): string {
  if (phase === 'plan') return 'Plan'
  if (phase === 'do') return 'Do'
  if (phase === 'check') return 'Check'
  if (phase === 'act') return 'Act'
  return 'No phase'
}

/**
 * Deming-cycle colours for step headers. Unset returns neutral classes so an
 * un-phased step reads as un-phased rather than as an arbitrary colour.
 */
export function pdcaPhaseClasses(phase: JobStepPdcaPhase | null): string {
  if (phase === 'plan') return 'bg-sky-500/10 text-sky-900 dark:text-sky-100 border-sky-500/40'
  if (phase === 'do') return 'bg-emerald-500/10 text-emerald-900 dark:text-emerald-100 border-emerald-500/40'
  if (phase === 'check') return 'bg-amber-500/10 text-amber-900 dark:text-amber-100 border-amber-500/40'
  if (phase === 'act') return 'bg-violet-500/10 text-violet-900 dark:text-violet-100 border-violet-500/40'
  return 'bg-muted/20 text-muted-foreground border-border'
}

/** Next phase in the Deming cycle; from unset, start at `plan`. Cycles act → null. */
export function nextPdcaPhase(phase: JobStepPdcaPhase | null): JobStepPdcaPhase | null {
  if (phase === null) return 'plan'
  if (phase === 'plan') return 'do'
  if (phase === 'do') return 'check'
  if (phase === 'check') return 'act'
  return null
}

/* -------------------------------------------------------------------------- */
/* JL-UX-W2 — nesting, derived from job_cycle links only                      */
/* -------------------------------------------------------------------------- */

export interface JobLaneNestChip {
  targetJobTypeId: number
  label: string
}

/**
 * Nested job cycles reachable from a lane, derived from the lane's cells.
 *
 * There is deliberately no `nested_job_type_id` on `job_lanes`: the
 * `job_cycle` cell links are the only SSOT, so the chip is computed and can
 * never disagree with the links a user can see and delete.
 */
export function deriveLaneNestChips(
  cells: readonly JobCell[],
  laneId: number,
  jobTypes: readonly JobType[] = [],
): JobLaneNestChip[] {
  const namesById = new Map<number, string>()
  for (const jt of jobTypes) namesById.set(jt.id, jt.name)

  const seen = new Set<number>()
  const chips: JobLaneNestChip[] = []
  for (const cell of cells) {
    if (cell.lane_id !== laneId) continue
    for (const link of cell.links ?? []) {
      if (link.kind !== 'job_cycle') continue
      const target = link.target_job_type_id
      if (typeof target !== 'number' || !Number.isFinite(target) || target <= 0) continue
      if (seen.has(target)) continue
      seen.add(target)
      chips.push({
        targetJobTypeId: target,
        label: namesById.get(target) ?? link.label ?? `Job cycle #${target}`,
      })
    }
  }
  return chips
}

/** All job cycles nested anywhere in the loaded pack (any lane, any step). */
export function deriveNestedJobTypeIds(cells: readonly JobCell[]): number[] {
  const seen = new Set<number>()
  const ordered: number[] = []
  for (const cell of cells) {
    for (const link of cell.links ?? []) {
      if (link.kind !== 'job_cycle') continue
      const target = link.target_job_type_id
      if (typeof target !== 'number' || !Number.isFinite(target) || target <= 0) continue
      if (seen.has(target)) continue
      seen.add(target)
      ordered.push(target)
    }
  }
  return ordered
}

/* -------------------------------------------------------------------------- */
/* JL-UX-W2 — drill-in / drill-out breadcrumb                                 */
/* -------------------------------------------------------------------------- */

export interface JobCycleBreadcrumbItem {
  jobTypeId: number
  label: string
  isCurrent: boolean
}

/** Push the cycle being left onto the trail. Ignores repeats and bad ids. */
export function pushDrillTrail(trail: readonly number[], fromJobTypeId: number | null): number[] {
  if (fromJobTypeId == null || !Number.isFinite(fromJobTypeId) || fromJobTypeId <= 0) {
    return trail.slice()
  }
  if (trail[trail.length - 1] === fromJobTypeId) return trail.slice()
  return [...trail, fromJobTypeId]
}

/** Drill out to trail position `index`; the entries after it are discarded. */
export function truncateDrillTrail(trail: readonly number[], index: number): number[] {
  if (!Number.isFinite(index) || index < 0) return []
  return trail.slice(0, index)
}

/**
 * Breadcrumb for the active drill path. Trail entries are ancestors in visit
 * order; the current cycle is always last and marked `isCurrent`.
 */
export function buildJobCycleBreadcrumb(input: {
  trail: readonly number[]
  currentJobTypeId: number | null
  jobTypes: readonly JobType[]
}): JobCycleBreadcrumbItem[] {
  const namesById = new Map<number, string>()
  for (const jt of input.jobTypes) namesById.set(jt.id, jt.name)
  const label = (id: number) => namesById.get(id) ?? `Job cycle #${id}`

  const items: JobCycleBreadcrumbItem[] = input.trail.map((id) => ({
    jobTypeId: id,
    label: label(id),
    isCurrent: false,
  }))
  if (input.currentJobTypeId != null) {
    items.push({
      jobTypeId: input.currentJobTypeId,
      label: label(input.currentJobTypeId),
      isCurrent: true,
    })
  }
  return items
}

/** Only worth rendering once there is somewhere to drill back out to. */
export function shouldShowJobCycleBreadcrumb(trail: readonly number[]): boolean {
  return trail.length > 0
}

/* -------------------------------------------------------------------------- */
/* JL-UX-W2 — axis reorder over the existing PATCH APIs                       */
/* -------------------------------------------------------------------------- */

export interface AxisOrderUpdate {
  id: number
  sort_order: number
}

/**
 * `sort_order` values that move one axis up or down by one place.
 *
 * Returns `[]` at the ends of the list, so the caller issues no PATCH rather
 * than a no-op write. Positions are renumbered densely from 0 because stored
 * `sort_order` values can be duplicated or sparse — swapping the two stored
 * numbers would not move anything when they are equal.
 */
export function computeAxisReorder<T extends { id: number; sort_order: number; name: string }>(
  items: readonly T[],
  id: number,
  direction: 'up' | 'down',
): AxisOrderUpdate[] {
  const ordered = sortAxesByOrder(items)
  const index = ordered.findIndex((item) => item.id === id)
  if (index < 0) return []
  const target = direction === 'up' ? index - 1 : index + 1
  if (target < 0 || target >= ordered.length) return []

  const swapped = ordered.slice()
  const moving = swapped[index]
  swapped[index] = swapped[target]
  swapped[target] = moving

  return swapped
    .map((item, position) => ({ id: item.id, sort_order: position }))
    .filter((update) => {
      const before = ordered.find((item) => item.id === update.id)
      return !before || before.sort_order !== update.sort_order
    })
}

/* -------------------------------------------------------------------------- */
/* JL-UX-W3 — freshness toggle                                                */
/* -------------------------------------------------------------------------- */

export const JOB_LIFECYCLE_FRESHNESS_STORAGE_KEY = 'job_lifecycle_freshness'

/** Default OFF: the composer stays calm until an operator asks for status. */
export const DEFAULT_JOB_LIFECYCLE_FRESHNESS = false

/** Matches `MAX_FRESHNESS_DOCUMENT_IDS` on the service. */
export const FRESHNESS_ID_REQUEST_LIMIT = 200

export function parseStoredJobLifecycleFreshness(raw: string | null | undefined): boolean | null {
  if (raw === 'on') return true
  if (raw === 'off') return false
  return null
}

export function readStoredJobLifecycleFreshness(
  storage: Pick<Storage, 'getItem'> | null | undefined = typeof localStorage !== 'undefined'
    ? localStorage
    : null,
): boolean | null {
  if (!storage) return null
  try {
    return parseStoredJobLifecycleFreshness(storage.getItem(JOB_LIFECYCLE_FRESHNESS_STORAGE_KEY))
  } catch {
    return null
  }
}

export function writeStoredJobLifecycleFreshness(
  enabled: boolean,
  storage: Pick<Storage, 'setItem'> | null | undefined = typeof localStorage !== 'undefined'
    ? localStorage
    : null,
): void {
  if (!storage) return
  try {
    storage.setItem(JOB_LIFECYCLE_FRESHNESS_STORAGE_KEY, enabled ? 'on' : 'off')
  } catch {
    // Storage may be unavailable — ignore.
  }
}

export function resolveJobLifecycleFreshness(
  preferred: boolean | null | undefined,
  fallback: boolean = DEFAULT_JOB_LIFECYCLE_FRESHNESS,
): boolean {
  return typeof preferred === 'boolean' ? preferred : fallback
}

/* -------------------------------------------------------------------------- */
/* JL-UX-W3 — document freshness presentation                                 */
/* -------------------------------------------------------------------------- */

/**
 * Library statuses that mean "withdrawn from active use".
 *
 * Mirrors `OBSOLETE_LIBRARY_STATUSES` on the service so the tray can label a
 * document the list API already told us is obsolete, without waiting for the
 * freshness lookup. Everything date-driven is left to the server — duplicating
 * review-window arithmetic in the client is how the two would drift.
 */
export const OBSOLETE_LIBRARY_STATUSES: readonly string[] = [
  'obsolete',
  'superseded',
  'retired',
  'archived',
] as const

export function isObsoleteLibraryStatus(status: string | null | undefined): boolean {
  if (typeof status !== 'string') return false
  return OBSOLETE_LIBRARY_STATUSES.includes(status.trim().toLowerCase())
}

export function freshnessStateLabel(state: JobDocumentFreshnessState): string {
  if (state === 'current') return 'Current'
  if (state === 'due_soon') return 'Review due'
  if (state === 'overdue') return 'Overdue'
  if (state === 'obsolete') return 'Obsolete'
  return 'Unknown'
}

export function freshnessStateClasses(state: JobDocumentFreshnessState): string {
  if (state === 'current') {
    return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100'
  }
  if (state === 'due_soon') {
    return 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100'
  }
  if (state === 'overdue' || state === 'obsolete') {
    return 'border-destructive/40 bg-destructive/10 text-destructive'
  }
  return 'border-border bg-muted/30 text-muted-foreground'
}

/** Plain-language tooltip naming the field the verdict came from. */
export function freshnessTitle(item: JobDocumentFreshness | null | undefined): string {
  if (!item) return 'Freshness unknown — status not loaded for this document.'
  if (item.reason === 'document_not_found') {
    return 'Freshness unknown — this document is not visible in your library.'
  }
  if (item.reason === 'obsolete_controlled_status') {
    return `Obsolete in Document Control (status ${item.controlled_status ?? 'obsolete'}).`
  }
  if (item.reason === 'obsolete_library_status') {
    return `Obsolete in the Library (status ${item.library_status ?? 'obsolete'}).`
  }
  if (item.reason === 'no_review_date') {
    return 'Freshness unknown — no review date recorded in Library or Document Control.'
  }
  const when = item.review_date ? new Date(item.review_date).toLocaleDateString() : 'unknown date'
  if (item.reason === 'review_overdue') return `Review was due ${when}.`
  if (item.reason === 'review_due_soon') return `Review due ${when}.`
  return `Next review ${when}.`
}

export function buildFreshnessIndex(
  items: readonly JobDocumentFreshness[],
): Map<number, JobDocumentFreshness> {
  const map = new Map<number, JobDocumentFreshness>()
  for (const item of items) map.set(item.library_document_id, item)
  return map
}

/** Merge a freshness page into the running index without dropping known ids. */
export function mergeFreshnessIndex(
  previous: ReadonlyMap<number, JobDocumentFreshness>,
  items: readonly JobDocumentFreshness[],
): Map<number, JobDocumentFreshness> {
  const merged = new Map(previous)
  for (const item of items) merged.set(item.library_document_id, item)
  return merged
}

/**
 * Ids the composer can currently see: the loaded tray page plus every document
 * referenced by a cell. Deduped and capped so one request covers the view.
 */
export function collectFreshnessDocumentIds(input: {
  libraryDocs: readonly JobLifecycleLibraryDoc[]
  cells: readonly JobCell[]
  limit?: number
}): number[] {
  const seen = new Set<number>()
  const ordered: number[] = []
  const push = (id: unknown) => {
    if (typeof id !== 'number' || !Number.isFinite(id) || id <= 0) return
    if (seen.has(id)) return
    seen.add(id)
    ordered.push(id)
  }
  // Cell refs first: those chips are the ones that drive attach decisions, so
  // they must not be the ones dropped when the cap bites.
  for (const cell of input.cells) {
    for (const id of cell.library_document_ids ?? []) push(id)
  }
  for (const doc of input.libraryDocs) push(doc.id)
  return ordered.slice(0, input.limit ?? FRESHNESS_ID_REQUEST_LIMIT)
}

/**
 * Ids not yet accounted for — the only ones worth another request.
 *
 * Takes anything with `has()` so the caller can pass either the verdict index
 * or the set of ids already asked for, which is what stops a re-render from
 * re-issuing a request that is still in flight.
 */
export function missingFreshnessIds(
  known: { has(id: number): boolean },
  ids: readonly number[],
): number[] {
  return ids.filter((id) => !known.has(id))
}

/**
 * Whether a drop should be refused before it reaches the API.
 *
 * The server enforces this too and is the authority; this only spares the
 * operator a round trip when the tray already shows the document as obsolete.
 */
export function obsoleteAttachBlock(input: {
  documentId: number
  freshness: ReadonlyMap<number, JobDocumentFreshness>
  libraryStatus?: string | null
}): { blocked: boolean; reason: string } {
  const verdict = input.freshness.get(input.documentId)
  if (verdict?.is_obsolete) {
    return {
      blocked: true,
      reason: `Obsolete documents cannot be attached — ${freshnessTitle(verdict)} Supersede it in the Library first.`,
    }
  }
  if (!verdict && isObsoleteLibraryStatus(input.libraryStatus)) {
    return {
      blocked: true,
      reason: `Obsolete documents cannot be attached — the Library records this document as ${input.libraryStatus}. Supersede it in the Library first.`,
    }
  }
  return { blocked: false, reason: '' }
}

/* -------------------------------------------------------------------------- */
/* JL-UX-W3 — audit lapse cues                                                */
/* -------------------------------------------------------------------------- */

export function auditLapseLabel(state: JobAuditLapseState): string {
  if (state === 'current') return 'In date'
  if (state === 'due_soon') return 'Audit due'
  if (state === 'lapsed') return 'Lapsed'
  return 'Unknown'
}

export function auditLapseClasses(state: JobAuditLapseState): string {
  if (state === 'current') {
    return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100'
  }
  if (state === 'due_soon') {
    return 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100'
  }
  if (state === 'lapsed') return 'border-destructive/40 bg-destructive/10 text-destructive'
  return 'border-border bg-muted/30 text-muted-foreground'
}

/** Names the evidence, so an `unknown` reads as "we cannot tell" not "fine". */
export function auditLapseTitle(
  lapse: { state: JobAuditLapseState; reason: string; next_due_at?: string | null } | null | undefined,
): string {
  if (!lapse) return 'Audit cadence unknown — no run data loaded for this link.'
  if (lapse.reason === 'no_audit_run') {
    return 'Audit cadence unknown — the linked run is not readable.'
  }
  if (lapse.reason === 'no_audit_cadence') {
    return 'Audit cadence unknown — the template records no repeat frequency (ad-hoc audits never lapse).'
  }
  if (lapse.reason === 'audit_not_completed') {
    return 'Audit cadence unknown — the run has not completed and has no due date.'
  }
  const when = lapse.next_due_at ? new Date(lapse.next_due_at).toLocaleDateString() : 'unknown date'
  if (lapse.reason === 'run_past_due') return `Audit run was due ${when} and has not completed.`
  if (lapse.reason === 'run_due_soon') return `Audit run is due ${when}.`
  if (lapse.reason === 'run_within_due') return `Audit run is due ${when}.`
  if (lapse.reason === 'cadence_overdue') return `Repeat audit was due ${when}.`
  if (lapse.reason === 'cadence_due_soon') return `Repeat audit due ${when}.`
  return `Next audit due ${when}.`
}
