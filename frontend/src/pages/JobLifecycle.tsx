/**
 * Job Lifecycle swimlane composer (JL-2 / ADR-0022).
 *
 * Flag-gated by `job_lifecycle` (default OFF). Matrix · Transpose · Phase are
 * views over the same JL-1 cells. Library DnD attaches document ID refs only.
 * Connections reuse Entity360 (X-1); coach reuses GraphCoach surface
 * `job_lifecycle` (X-2). Never invents a second document SSOT or org chart.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type PointerEvent as ReactPointerEvent } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import {
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Copy,
  GitBranch,
  Loader2,
  Plus,
  ShieldCheck,
  Trash2,
} from 'lucide-react'
import api, { getApiErrorMessage, jobLifecycleApi } from '../api/client'
import type {
  JobCell,
  JobCellLink,
  JobCellReadinessItem,
  JobDocumentFreshness,
  JobLane,
  JobStep,
  JobStepPdcaPhase,
  JobType,
  JobTypeBaseline,
  JobTypeBaselineDiffResponse,
} from '../api/jobLifecycleClient'
import { useFeatureFlag } from '../hooks/useFeatureFlag'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
import { Entity360Strip, GraphCoach } from '../components/graph'
import JobCellLinks from '../components/jobLifecycle/JobCellLinks'
import JobGraphPanel from '../components/jobLifecycle/JobGraphPanel'
import {
  parseLibraryDocumentDrag,
  setLibraryDocumentDragData,
  shouldEnableLibraryDocumentDrag,
} from '../components/graph/documentGraphDndHelpers'
import {
  DEFAULT_JOB_LIFECYCLE_PANEL_WIDTHS,
  DEFAULT_JOB_LIFECYCLE_VIEW_MODE,
  JOB_LIFECYCLE_PANEL_BOUNDS,
  JOB_LIFECYCLE_PERMISSION_HEALTH_COPY,
  auditLapseClasses,
  auditLapseLabel,
  auditLapseTitle,
  availableJobLifecycleViewModes,
  baselineViewingBanner,
  buildAxisCode,
  buildCellIndex,
  buildJobCycleBreadcrumb,
  cellKey,
  clampJobLifecyclePanelWidth,
  collectFreshnessDocumentIds,
  computeAxisReorder,
  conflictBannerCopy,
  countUnreadyCells,
  deriveLaneNestChips,
  detachDocumentRef,
  emptyComposerCopy,
  freshnessStateClasses,
  freshnessStateLabel,
  freshnessTitle,
  ifMatchToken,
  isConflictApiError,
  isForbiddenApiError,
  isJobLifecycleGraphViewMode,
  jobLifecycleViewModeLabel,
  libraryDocLabel,
  mergeFreshnessIndex,
  missingFreshnessIds,
  nextPdcaPhase,
  obsoleteAttachBlock,
  pdcaPhaseClasses,
  pdcaPhaseLabel,
  pushDrillTrail,
  readStoredJobLifecycleFreshness,
  readStoredJobLifecyclePanelWidths,
  readStoredJobLifecycleViewMode,
  readinessStateClasses,
  readinessStateLabel,
  readinessTitle,
  resolveAvailableViewMode,
  resolveDndCellAttach,
  resolveJobLifecycleFreshness,
  resolveJobLifecyclePanelWidths,
  resolveJobLifecycleViewMode,
  resolvePdcaPhase,
  resolveSelectedJobTypeId,
  resolveSelectedStepId,
  resolveSwimlaneAxes,
  shouldFetchJobLifecycle,
  shouldShowBaselineBanner,
  shouldShowJobCycleBreadcrumb,
  shouldShowJobLifecycle,
  sortAxesByOrder,
  summariseBaselineDiff,
  truncateDrillTrail,
  writeStoredJobLifecycleFreshness,
  writeStoredJobLifecyclePanelWidths,
  writeStoredJobLifecycleViewMode,
  type JobLifecycleLibraryDoc,
  type JobLifecyclePanelWidths,
  type JobLifecycleViewMode,
} from './jobLifecycleHelpers'

interface LibraryDocumentPage {
  items?: Array<{
    id: number
    title: string
    reference_number?: string | null
    status?: string | null
    review_date?: string | null
  }>
  total?: number
  page?: number
  page_size?: number
  pages?: number
}

export default function JobLifecycle() {
  const jobLifecycleEnabled = useFeatureFlag('job_lifecycle')
  const jobCellLinksEnabled = useFeatureFlag('job_cell_links')
  const dndProposeEnabled = useFeatureFlag('document_graph_dnd_propose')
  const visible = shouldShowJobLifecycle(jobLifecycleEnabled)
  const shouldFetch = shouldFetchJobLifecycle(jobLifecycleEnabled)
  const libraryDragEnabled = shouldEnableLibraryDocumentDrag(dndProposeEnabled)

  const { stepId: stepIdParam, jobTypeId: jobTypeIdParam } = useParams<{
    stepId?: string
    jobTypeId?: string
  }>()
  const preferredStepId = useMemo(() => {
    const n = Number(stepIdParam)
    return Number.isFinite(n) && n > 0 ? n : null
  }, [stepIdParam])
  const preferredJobTypeId = useMemo(() => {
    const n = Number(jobTypeIdParam)
    return Number.isFinite(n) && n > 0 ? n : null
  }, [jobTypeIdParam])

  const [jobTypes, setJobTypes] = useState<JobType[]>([])
  const [lanes, setLanes] = useState<JobLane[]>([])
  const [steps, setSteps] = useState<JobStep[]>([])
  const [cells, setCells] = useState<JobCell[]>([])
  const [libraryDocs, setLibraryDocs] = useState<JobLifecycleLibraryDoc[]>([])
  const [selectedJobTypeId, setSelectedJobTypeId] = useState<number | null>(preferredJobTypeId)
  /** Ancestor cycles visited by drilling in — the breadcrumb's drill-out path. */
  const [drillTrail, setDrillTrail] = useState<number[]>([])
  const [selectedStepId, setSelectedStepId] = useState<number | null>(preferredStepId)
  const [selectedLaneId, setSelectedLaneId] = useState<number | null>(null)
  const [viewMode, setViewMode] = useState<JobLifecycleViewMode>(() =>
    resolveJobLifecycleViewMode(readStoredJobLifecycleViewMode(), DEFAULT_JOB_LIFECYCLE_VIEW_MODE),
  )
  const [freshnessOn, setFreshnessOn] = useState<boolean>(() =>
    resolveJobLifecycleFreshness(readStoredJobLifecycleFreshness()),
  )
  const [freshness, setFreshness] = useState<ReadonlyMap<number, JobDocumentFreshness>>(
    () => new Map(),
  )
  const [freshnessLoading, setFreshnessLoading] = useState(false)
  const [freshnessError, setFreshnessError] = useState<string | null>(null)
  /** Ids already asked for — keeps the toggle from re-requesting on every render. */
  const freshnessAskedRef = useRef<Set<number>>(new Set())
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  /** JL-UX-W4 — set when a PATCH was refused because the row moved under us. */
  const [conflict, setConflict] = useState<string | null>(null)
  const [readiness, setReadiness] = useState<JobCellReadinessItem[]>([])
  const [readinessError, setReadinessError] = useState<string | null>(null)
  /** Bumped after a write so derived views re-read rather than going stale. */
  const [derivedNonce, setDerivedNonce] = useState(0)
  const [cloneName, setCloneName] = useState('')
  const [baselineLabel, setBaselineLabel] = useState('')
  const [baselines, setBaselines] = useState<JobTypeBaseline[]>([])
  const [viewingBaselineId, setViewingBaselineId] = useState<number | null>(null)
  const [baselineDiff, setBaselineDiff] = useState<JobTypeBaselineDiffResponse | null>(null)
  const [baselineBanner, setBaselineBanner] = useState<string | null>(null)
  const [dropHint, setDropHint] = useState<string | null>(null)
  const [newJobTypeName, setNewJobTypeName] = useState('')
  const [newLaneName, setNewLaneName] = useState('')
  const [newStepName, setNewStepName] = useState('')
  const [libraryFilter, setLibraryFilter] = useState('')
  const [libraryPage, setLibraryPage] = useState(1)
  const [libraryPages, setLibraryPages] = useState(1)
  const [libraryLoadingMore, setLibraryLoadingMore] = useState(false)
  const [permissionHealth, setPermissionHealth] = useState(false)
  const [panelWidths, setPanelWidths] = useState<JobLifecyclePanelWidths>(() =>
    resolveJobLifecyclePanelWidths(readStoredJobLifecyclePanelWidths(), DEFAULT_JOB_LIFECYCLE_PANEL_WIDTHS),
  )
  const resizeRef = useRef<{ side: 'left' | 'right'; startX: number; startWidth: number } | null>(
    null,
  )

  const cellIndex = useMemo(() => buildCellIndex(cells), [cells])

  const readinessIndex = useMemo(() => {
    const map = new Map<string, JobCellReadinessItem>()
    for (const item of readiness) map.set(cellKey(item.lane_id, item.step_id), item)
    return map
  }, [readiness])

  const unreadyCount = useMemo(() => countUnreadyCells(readiness), [readiness])

  const handleLinksChange = useCallback(
    (newLinks: JobCellLink[]) => {
      if (selectedLaneId == null || selectedStepId == null) return
      const laneId = selectedLaneId
      const stepId = selectedStepId
      setCells((prev) =>
        prev.map((c) =>
          c.lane_id === laneId && c.step_id === stepId ? { ...c, links: newLinks } : c,
        ),
      )
    },
    [selectedLaneId, selectedStepId],
  )

  const selectedCellLinks = useMemo(() => {
    if (selectedLaneId == null || selectedStepId == null) return [] as JobCellLink[]
    return cellIndex.get(cellKey(selectedLaneId, selectedStepId))?.links ?? []
  }, [cellIndex, selectedLaneId, selectedStepId])

  const onPanelPointerDown = (side: 'left' | 'right', event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    resizeRef.current = {
      side,
      startX: event.clientX,
      startWidth: side === 'left' ? panelWidths.left : panelWidths.right,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const onPanelPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const active = resizeRef.current
    if (!active) return
    const delta = event.clientX - active.startX
    setPanelWidths((prev) => {
      if (active.side === 'left') {
        const left = clampJobLifecyclePanelWidth(
          active.startWidth + delta,
          JOB_LIFECYCLE_PANEL_BOUNDS.leftMin,
          JOB_LIFECYCLE_PANEL_BOUNDS.leftMax,
        )
        const next = { ...prev, left }
        writeStoredJobLifecyclePanelWidths(next)
        return next
      }
      const right = clampJobLifecyclePanelWidth(
        active.startWidth - delta,
        JOB_LIFECYCLE_PANEL_BOUNDS.rightMin,
        JOB_LIFECYCLE_PANEL_BOUNDS.rightMax,
      )
      const next = { ...prev, right }
      writeStoredJobLifecyclePanelWidths(next)
      return next
    })
  }

  const onPanelPointerUp = () => {
    resizeRef.current = null
  }
  const docsById = useMemo(() => {
    const map = new Map<number, JobLifecycleLibraryDoc>()
    for (const doc of libraryDocs) map.set(doc.id, doc)
    return map
  }, [libraryDocs])

  const orderedJobTypes = useMemo(() => sortAxesByOrder(jobTypes), [jobTypes])
  const orderedLanes = useMemo(() => sortAxesByOrder(lanes), [lanes])
  const orderedSteps = useMemo(() => sortAxesByOrder(steps), [steps])

  const effectiveJobTypeId = useMemo(
    () => resolveSelectedJobTypeId(selectedJobTypeId ?? preferredJobTypeId, jobTypes),
    [selectedJobTypeId, preferredJobTypeId, jobTypes],
  )
  const effectiveStepId = useMemo(
    () => resolveSelectedStepId(selectedStepId ?? preferredStepId, steps),
    [selectedStepId, preferredStepId, steps],
  )

  const axes = useMemo(
    () =>
      resolveSwimlaneAxes({
        viewMode,
        lanes: orderedLanes,
        steps: orderedSteps,
        phaseStepId: effectiveStepId,
      }),
    [viewMode, orderedLanes, orderedSteps, effectiveStepId],
  )

  const filteredLibrary = useMemo(() => {
    const q = libraryFilter.trim().toLowerCase()
    if (!q) return libraryDocs
    return libraryDocs.filter((doc) => {
      const hay = `${doc.title} ${doc.reference ?? ''}`.toLowerCase()
      return hay.includes(q)
    })
  }, [libraryDocs, libraryFilter])

  const loadLibraryPage = useCallback(
    async (page: number, append: boolean) => {
      const pageSize = 50
      const res = await api.get<LibraryDocumentPage>(
        `/api/v1/documents/?page=${page}&page_size=${pageSize}`,
      )
      const items = res.data.items ?? []
      // Status and review date come back on every list row; carrying them
      // through ingest is what lets the tray label an obsolete document even
      // before the authoritative freshness lookup answers.
      const mapped: JobLifecycleLibraryDoc[] = items.map((item) => ({
        id: item.id,
        title: item.title,
        reference: item.reference_number ?? null,
        status: item.status ?? null,
        review_date: item.review_date ?? null,
      }))
      setLibraryPages(res.data.pages ?? 1)
      setLibraryPage(page)
      setLibraryDocs((prev) => (append ? [...prev, ...mapped] : mapped))
    },
    [],
  )

  const loadPack = useCallback(async () => {
    if (!shouldFetch) {
      setJobTypes([])
      setLanes([])
      setSteps([])
      setCells([])
      setLibraryDocs([])
      setLibraryPage(1)
      setLibraryPages(1)
      setPermissionHealth(false)
      setError(null)
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const typesRes = await jobLifecycleApi.listJobTypes()
      setPermissionHealth(false)
      setJobTypes(typesRes.data.items ?? [])
      try {
        await loadLibraryPage(1, false)
      } catch (libraryErr) {
        setLibraryDocs([])
        if (isForbiddenApiError(libraryErr)) {
          // Library tray is helpful but not required to author axes.
          setDropHint('Library tray could not load — document:read may be missing.')
        }
      }
    } catch (err) {
      setJobTypes([])
      setLibraryDocs([])
      if (isForbiddenApiError(err)) {
        setPermissionHealth(true)
        setError(JOB_LIFECYCLE_PERMISSION_HEALTH_COPY)
      } else {
        setPermissionHealth(false)
        setError(getApiErrorMessage(err))
      }
    } finally {
      setLoading(false)
    }
  }, [shouldFetch, loadLibraryPage])

  const loadMoreLibrary = useCallback(async () => {
    if (libraryLoadingMore || libraryPage >= libraryPages) return
    setLibraryLoadingMore(true)
    try {
      await loadLibraryPage(libraryPage + 1, true)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setLibraryLoadingMore(false)
    }
  }, [libraryLoadingMore, libraryPage, libraryPages, loadLibraryPage])

  const loadAxesForType = useCallback(
    async (jobTypeId: number) => {
      if (!shouldFetch || !jobTypeId) {
        setLanes([])
        setSteps([])
        setCells([])
        setBaselines([])
        setViewingBaselineId(null)
        setBaselineDiff(null)
        setBaselineBanner(null)
        return
      }
      setLoading(true)
      setError(null)
      try {
        const [lanesRes, stepsRes, cellsRes, baselinesRes] = await Promise.all([
          jobLifecycleApi.listLanes(jobTypeId),
          jobLifecycleApi.listSteps(jobTypeId),
          jobLifecycleApi.listCells(jobTypeId),
          jobLifecycleApi.listBaselines(jobTypeId),
        ])
        setLanes(lanesRes.data.items ?? [])
        setSteps(stepsRes.data.items ?? [])
        setCells(cellsRes.data.items ?? [])
        setBaselines(baselinesRes.data.items ?? [])
        setViewingBaselineId(null)
        setBaselineDiff(null)
        setBaselineBanner(null)
      } catch (err) {
        setLanes([])
        setSteps([])
        setCells([])
        setBaselines([])
        setViewingBaselineId(null)
        setBaselineDiff(null)
        setBaselineBanner(null)
        if (isForbiddenApiError(err)) {
          setPermissionHealth(true)
          setError(JOB_LIFECYCLE_PERMISSION_HEALTH_COPY)
        } else {
          setError(getApiErrorMessage(err))
        }
      } finally {
        setLoading(false)
      }
    },
    [shouldFetch],
  )

  useEffect(() => {
    void loadPack()
  }, [loadPack])

  useEffect(() => {
    if (effectiveJobTypeId != null) {
      if (selectedJobTypeId !== effectiveJobTypeId) {
        setSelectedJobTypeId(effectiveJobTypeId)
      }
      void loadAxesForType(effectiveJobTypeId)
    } else {
      setLanes([])
      setSteps([])
      setCells([])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-fetch when type id changes
  }, [effectiveJobTypeId, loadAxesForType])

  /** Everything the composer can currently show a chip for. */
  const freshnessIds = useMemo(
    () => collectFreshnessDocumentIds({ libraryDocs, cells }),
    [libraryDocs, cells],
  )

  useEffect(() => {
    if (!freshnessOn || !shouldFetch) return
    const wanted = missingFreshnessIds(freshnessAskedRef.current, freshnessIds)
    if (wanted.length === 0) return
    for (const id of wanted) freshnessAskedRef.current.add(id)

    let cancelled = false
    setFreshnessLoading(true)
    jobLifecycleApi
      .listDocumentFreshness(wanted)
      .then((res) => {
        if (cancelled) return
        setFreshness((prev) => mergeFreshnessIndex(prev, res.data.items ?? []))
        setFreshnessError(null)
      })
      .catch((err) => {
        // Drop the claim on these ids so a later render can retry rather than
        // leaving them permanently blank.
        for (const id of wanted) freshnessAskedRef.current.delete(id)
        if (!cancelled) setFreshnessError(getApiErrorMessage(err))
      })
      .finally(() => {
        if (!cancelled) setFreshnessLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [freshnessOn, shouldFetch, freshnessIds])

  /** Nothing is mandatory here, so there is no readiness question to ask. */
  const hasMandatoryCells = useMemo(
    () => cells.some((cell) => Boolean(cell.requires_evidence)),
    [cells],
  )

  /**
   * Readiness for the pack's mandatory cells (JL-UX-W4).
   *
   * Derived on the server on every read — nothing here is cached into the JL
   * tables. `assure` follows the Freshness toggle, so an operator who has not
   * asked for document status is shown presence only rather than a verdict the
   * composer cannot back up.
   */
  useEffect(() => {
    if (!shouldFetch || effectiveJobTypeId == null || !hasMandatoryCells) {
      setReadiness([])
      setReadinessError(null)
      return
    }
    let cancelled = false
    jobLifecycleApi
      .listEvidenceReadiness(effectiveJobTypeId, freshnessOn)
      .then((res) => {
        if (cancelled) return
        setReadiness(res.data.items ?? [])
        setReadinessError(null)
      })
      .catch((err) => {
        if (cancelled) return
        setReadiness([])
        setReadinessError(getApiErrorMessage(err))
      })
    return () => {
      cancelled = true
    }
  }, [shouldFetch, effectiveJobTypeId, freshnessOn, derivedNonce, hasMandatoryCells])

  /** A mode withdrawn by a closed flag must not survive in local storage. */
  useEffect(() => {
    setViewMode((prev) => resolveAvailableViewMode(prev, jobCellLinksEnabled))
  }, [jobCellLinksEnabled])

  useEffect(() => {
    if (preferredStepId != null) {
      setSelectedStepId(preferredStepId)
      setViewMode('phase')
    }
  }, [preferredStepId])

  useEffect(() => {
    if (preferredJobTypeId != null) {
      setSelectedJobTypeId(preferredJobTypeId)
    }
  }, [preferredJobTypeId])

  const breadcrumb = useMemo(
    () =>
      buildJobCycleBreadcrumb({
        trail: drillTrail,
        currentJobTypeId: effectiveJobTypeId,
        jobTypes,
      }),
    [drillTrail, effectiveJobTypeId, jobTypes],
  )

  if (!visible) {
    return <Navigate to="/documents" replace />
  }

  const setMode = (next: JobLifecycleViewMode) => {
    const allowed = resolveAvailableViewMode(next, jobCellLinksEnabled)
    setViewMode(allowed)
    writeStoredJobLifecycleViewMode(allowed)
  }

  const graphMode = isJobLifecycleGraphViewMode(viewMode)

  const toggleFreshness = () => {
    const next = !freshnessOn
    setFreshnessOn(next)
    writeStoredJobLifecycleFreshness(next)
    if (!next) setFreshnessError(null)
  }

  /**
   * Freshness chip for a document, or `null` when the composer is calm.
   *
   * With the toggle ON and no verdict yet the chip still renders, as
   * "Unknown" — a blank space would read as "fine".
   */
  const renderFreshnessChip = (documentId: number, testId: string) => {
    if (!freshnessOn) return null
    const verdict = freshness.get(documentId)
    const state = verdict?.state ?? 'unknown'
    return (
      <span
        className={`shrink-0 rounded-full border px-1.5 py-0 text-[9px] uppercase tracking-wide ${freshnessStateClasses(state)}`}
        data-testid={testId}
        data-freshness-state={state}
        title={freshnessTitle(verdict)}
      >
        {freshnessStateLabel(state)}
      </span>
    )
  }

  /** Drill into a nested cycle, remembering where we came from. */
  const drillIntoCycle = (targetJobTypeId: number) => {
    if (targetJobTypeId === effectiveJobTypeId) return
    setDrillTrail((prev) => pushDrillTrail(prev, effectiveJobTypeId))
    setSelectedJobTypeId(targetJobTypeId)
    setSelectedLaneId(null)
    setSelectedStepId(null)
  }

  /** Drill back out to a breadcrumb ancestor; deeper entries are discarded. */
  const drillOutToTrailIndex = (index: number) => {
    const ancestor = drillTrail[index]
    if (ancestor == null) return
    setDrillTrail((prev) => truncateDrillTrail(prev, index))
    setSelectedJobTypeId(ancestor)
    setSelectedLaneId(null)
    setSelectedStepId(null)
  }

  /**
   * A refused edit is reported as a conflict, never as a generic failure.
   *
   * The distinction matters: a 409 means someone else's version is the one in
   * the database and this edit was dropped, so the operator has to look before
   * retrying rather than pressing the button again.
   */
  const reportWriteError = (err: unknown, label: string) => {
    if (isConflictApiError(err)) {
      setConflict(conflictBannerCopy(label))
      return
    }
    setError(getApiErrorMessage(err))
  }

  const reloadAfterConflict = () => {
    setConflict(null)
    setError(null)
    if (effectiveJobTypeId != null) void loadAxesForType(effectiveJobTypeId)
    setDerivedNonce((n) => n + 1)
  }

  const handleRenameLane = async (laneId: number, name: string) => {
    const trimmed = name.trim()
    if (!trimmed || saving) return
    const current = lanes.find((lane) => lane.id === laneId) ?? null
    setSaving(true)
    setError(null)
    setConflict(null)
    try {
      const res = await jobLifecycleApi.updateLane(
        laneId,
        { name: trimmed },
        { ifMatch: ifMatchToken(current) },
      )
      setLanes((prev) => prev.map((lane) => (lane.id === laneId ? res.data : lane)))
    } catch (err) {
      reportWriteError(err, current?.name ?? `Lane #${laneId}`)
    } finally {
      setSaving(false)
    }
  }

  const handleRenameStep = async (stepId: number, name: string) => {
    const trimmed = name.trim()
    if (!trimmed || saving) return
    const current = steps.find((step) => step.id === stepId) ?? null
    setSaving(true)
    setError(null)
    setConflict(null)
    try {
      const res = await jobLifecycleApi.updateStep(
        stepId,
        { name: trimmed },
        { ifMatch: ifMatchToken(current) },
      )
      setSteps((prev) => prev.map((step) => (step.id === stepId ? res.data : step)))
    } catch (err) {
      reportWriteError(err, current?.name ?? `Step #${stepId}`)
    } finally {
      setSaving(false)
    }
  }

  const handleReorderLane = async (laneId: number, direction: 'up' | 'down') => {
    const updates = computeAxisReorder(lanes, laneId, direction)
    if (updates.length === 0 || saving) return
    const moving = lanes.find((lane) => lane.id === laneId) ?? null
    setSaving(true)
    setError(null)
    setConflict(null)
    try {
      const results = await Promise.all(
        updates.map((update) =>
          jobLifecycleApi.updateLane(
            update.id,
            { sort_order: update.sort_order },
            { ifMatch: ifMatchToken(lanes.find((lane) => lane.id === update.id)) },
          ),
        ),
      )
      const byId = new Map(results.map((res) => [res.data.id, res.data]))
      setLanes((prev) => prev.map((lane) => byId.get(lane.id) ?? lane))
    } catch (err) {
      reportWriteError(err, moving?.name ?? `Lane #${laneId}`)
    } finally {
      setSaving(false)
    }
  }

  const handleReorderStep = async (stepId: number, direction: 'up' | 'down') => {
    const updates = computeAxisReorder(steps, stepId, direction)
    if (updates.length === 0 || saving) return
    const moving = steps.find((step) => step.id === stepId) ?? null
    setSaving(true)
    setError(null)
    setConflict(null)
    try {
      const results = await Promise.all(
        updates.map((update) =>
          jobLifecycleApi.updateStep(
            update.id,
            { sort_order: update.sort_order },
            { ifMatch: ifMatchToken(steps.find((step) => step.id === update.id)) },
          ),
        ),
      )
      const byId = new Map(results.map((res) => [res.data.id, res.data]))
      setSteps((prev) => prev.map((step) => byId.get(step.id) ?? step))
    } catch (err) {
      reportWriteError(err, moving?.name ?? `Step #${stepId}`)
    } finally {
      setSaving(false)
    }
  }

  /** Advance a step through plan → do → check → act → unset. */
  const handleCyclePdcaPhase = async (step: JobStep) => {
    if (saving) return
    const current = resolvePdcaPhase(step.pdca_phase)
    const next: JobStepPdcaPhase | null = nextPdcaPhase(current)
    setSaving(true)
    setError(null)
    setConflict(null)
    try {
      const res = await jobLifecycleApi.updateStep(
        step.id,
        { pdca_phase: next },
        { ifMatch: ifMatchToken(step) },
      )
      setSteps((prev) => prev.map((s) => (s.id === step.id ? res.data : s)))
    } catch (err) {
      reportWriteError(err, step.name)
    } finally {
      setSaving(false)
    }
  }

  /** Copy the active pack's axes into a new cycle. Cells are left empty. */
  const handleCloneJobType = async () => {
    const name = cloneName.trim()
    if (!name || !effectiveJobTypeId || saving) return
    setSaving(true)
    setError(null)
    setConflict(null)
    try {
      const res = await jobLifecycleApi.cloneJobType(effectiveJobTypeId, {
        code: buildAxisCode(name, 'job'),
        name,
      })
      setCloneName('')
      setJobTypes((prev) => [...prev, res.data.job_type])
      setSelectedJobTypeId(res.data.job_type.id)
      setSelectedLaneId(null)
      setSelectedStepId(null)
      setDropHint(
        `Cloned ${res.data.cloned_lane_count} lane(s) and ${res.data.cloned_step_count} step(s). Cells are empty — evidence is attached per pack, never copied.`,
      )
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  /** Freeze the live tip. Edit always stays on live — never on the snapshot. */
  const handleCreateBaseline = async () => {
    if (!effectiveJobTypeId || saving) return
    setSaving(true)
    setError(null)
    try {
      const res = await jobLifecycleApi.createBaseline(effectiveJobTypeId, {
        label: baselineLabel.trim() || null,
      })
      setBaselineLabel('')
      setBaselines((prev) => [res.data, ...prev])
      setDropHint(
        `Baseline #${res.data.id} captured. Viewing a baseline never redirects edits — live tip remains the source of truth.`,
      )
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const handleViewBaseline = async (baselineId: number) => {
    if (!effectiveJobTypeId) return
    setError(null)
    try {
      const [detail, diff] = await Promise.all([
        jobLifecycleApi.getBaseline(effectiveJobTypeId, baselineId),
        jobLifecycleApi.diffBaseline(effectiveJobTypeId, baselineId),
      ])
      setViewingBaselineId(baselineId)
      setBaselineBanner(detail.data.banner || baselineViewingBanner(detail.data))
      setBaselineDiff(diff.data)
    } catch (err) {
      setError(getApiErrorMessage(err))
    }
  }

  const handleClearBaselineView = () => {
    setViewingBaselineId(null)
    setBaselineDiff(null)
    setBaselineBanner(null)
  }

  /** Author the mandatory-evidence flag on one cell. The verdict stays derived. */
  const handleToggleCellRequirement = async (laneId: number, stepId: number) => {
    if (!effectiveJobTypeId || saving) return
    const current = Boolean(cellIndex.get(cellKey(laneId, stepId))?.requires_evidence)
    setSaving(true)
    setError(null)
    setConflict(null)
    try {
      const res = await jobLifecycleApi.patchCellRequirement(effectiveJobTypeId, laneId, stepId, {
        requires_evidence: !current,
      })
      setCells((prev) => {
        const without = prev.filter((c) => !(c.lane_id === laneId && c.step_id === stepId))
        return [...without, res.data]
      })
      setDerivedNonce((n) => n + 1)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const handleCreateJobType = async () => {
    const name = newJobTypeName.trim()
    if (!name || saving) return
    setSaving(true)
    setError(null)
    try {
      const res = await jobLifecycleApi.createJobType({
        code: buildAxisCode(name, 'job'),
        name,
        sort_order: jobTypes.length,
      })
      setNewJobTypeName('')
      setJobTypes((prev) => [...prev, res.data])
      setSelectedJobTypeId(res.data.id)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const handleCreateLane = async () => {
    const name = newLaneName.trim()
    if (!name || !effectiveJobTypeId || saving) return
    setSaving(true)
    setError(null)
    try {
      const res = await jobLifecycleApi.createLane(effectiveJobTypeId, {
        code: buildAxisCode(name, 'lane'),
        name,
        sort_order: lanes.length,
      })
      setNewLaneName('')
      setLanes((prev) => [...prev, res.data])
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const handleCreateStep = async () => {
    const name = newStepName.trim()
    if (!name || !effectiveJobTypeId || saving) return
    setSaving(true)
    setError(null)
    try {
      const res = await jobLifecycleApi.createStep(effectiveJobTypeId, {
        code: buildAxisCode(name, 'step'),
        name,
        sort_order: steps.length,
      })
      setNewStepName('')
      setSteps((prev) => [...prev, res.data])
      setSelectedStepId(res.data.id)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const persistCellDocs = async (
    laneId: number,
    stepId: number,
    library_document_ids: number[],
  ) => {
    if (!effectiveJobTypeId) return
    setSaving(true)
    setError(null)
    setDropHint(null)
    try {
      const res = await jobLifecycleApi.putCellDocuments(
        effectiveJobTypeId,
        laneId,
        stepId,
        { library_document_ids },
      )
      setCells((prev) => {
        const without = prev.filter((c) => !(c.lane_id === laneId && c.step_id === stepId))
        return [...without, res.data]
      })
      setSelectedLaneId(laneId)
      setSelectedStepId(stepId)
      setDerivedNonce((n) => n + 1)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const onCellDrop = async (event: DragEvent, laneId: number, stepId: number) => {
    event.preventDefault()
    const dragged = parseLibraryDocumentDrag(event.dataTransfer)
    const existing = cellIndex.get(cellKey(laneId, stepId))?.library_document_ids ?? []
    const result = resolveDndCellAttach({ dragged, existingIds: existing })
    if (!result.ok) {
      setDropHint(result.reason)
      return
    }
    // Enforcement, not decoration: this runs whether or not freshness display
    // is on. The API blocks it too — this only saves a round trip.
    if (dragged) {
      const block = obsoleteAttachBlock({
        documentId: dragged.documentId,
        freshness,
        libraryStatus: docsById.get(dragged.documentId)?.status,
      })
      if (block.blocked) {
        setDropHint(block.reason)
        return
      }
    }
    if (result.library_document_ids.length === existing.length) {
      setDropHint('Document already attached to this cell (reference only).')
      return
    }
    await persistCellDocs(laneId, stepId, result.library_document_ids)
  }

  const removeDocFromCell = async (laneId: number, stepId: number, documentId: number) => {
    const existing = cellIndex.get(cellKey(laneId, stepId))?.library_document_ids ?? []
    await persistCellDocs(laneId, stepId, detachDocumentRef(existing, documentId))
  }

  const onLibraryDragStart = (event: DragEvent, doc: JobLifecycleLibraryDoc) => {
    if (!libraryDragEnabled) {
      event.preventDefault()
      return
    }
    setLibraryDocumentDragData(event.dataTransfer, {
      documentId: doc.id,
      title: doc.title,
      reference: doc.reference,
    })
  }

  /**
   * PDCA colours only apply to the step axis — lanes have no Deming phase.
   * `pdca_phase` is read tolerantly so an unknown value reads as unset.
   */
  const axisHeaderPdcaClasses = (item: JobLane | JobStep, axis: 'lane' | 'step') => {
    if (axis !== 'step') return ''
    return pdcaPhaseClasses(resolvePdcaPhase((item as { pdca_phase?: unknown }).pdca_phase))
  }

  const axisPdcaLabel = (item: JobLane | JobStep, axis: 'lane' | 'step') => {
    if (axis !== 'step') return null
    return pdcaPhaseLabel(resolvePdcaPhase((item as { pdca_phase?: unknown }).pdca_phase))
  }

  const cellLaneStep = (row: JobLane | JobStep, column: JobLane | JobStep) => {
    if (axes.rowAxis === 'lane') {
      return { laneId: row.id, stepId: column.id }
    }
    return { laneId: column.id, stepId: row.id }
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="job-lifecycle-composer">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link to="/documents" data-testid="job-lifecycle-back">
                Library
              </Link>
            </Button>
            <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
              <GitBranch className="h-6 w-6 text-muted-foreground" />
              Job lifecycle
            </h1>
          </div>
          <p className="text-sm text-muted-foreground max-w-2xl">
            Compose swimlanes from JL process axes (job cycle · lane · step). Cells hold library
            document references only — never a second document store, never an org chart.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div
            className="inline-flex rounded-md border border-border p-0.5"
            role="group"
            aria-label="Swimlane view mode"
            data-testid="job-lifecycle-view-mode"
          >
            {availableJobLifecycleViewModes(jobCellLinksEnabled).map((mode) => (
              <Button
                key={mode}
                type="button"
                size="sm"
                variant={viewMode === mode ? 'default' : 'ghost'}
                aria-pressed={viewMode === mode}
                data-testid={`job-lifecycle-view-${mode}`}
                onClick={() => setMode(mode)}
              >
                {jobLifecycleViewModeLabel(mode)}
              </Button>
            ))}
          </div>
          <Button
            type="button"
            size="sm"
            variant={freshnessOn ? 'default' : 'outline'}
            aria-pressed={freshnessOn}
            data-testid="job-lifecycle-freshness-toggle"
            title={
              freshnessOn
                ? 'Showing document control status from the Library / Document Control record'
                : 'Show document control status on tray and cell references'
            }
            onClick={toggleFreshness}
          >
            {freshnessLoading ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <ShieldCheck className="mr-1 h-3.5 w-3.5" />
            )}
            Freshness {freshnessOn ? 'on' : 'off'}
          </Button>
        </div>
      </div>

      {shouldShowJobCycleBreadcrumb(drillTrail) ? (
        <nav
          className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground"
          aria-label="Job cycle drill path"
          data-testid="job-lifecycle-breadcrumb"
        >
          {breadcrumb.map((item, index) => (
            <span key={`${item.jobTypeId}-${index}`} className="flex items-center gap-1">
              {index > 0 ? <ChevronRight className="h-3 w-3 opacity-60" /> : null}
              {item.isCurrent ? (
                <span
                  className="font-medium text-foreground"
                  aria-current="page"
                  data-testid={`job-lifecycle-breadcrumb-current-${item.jobTypeId}`}
                >
                  {item.label}
                </span>
              ) : (
                <button
                  type="button"
                  className="hover:underline"
                  data-testid={`job-lifecycle-breadcrumb-${item.jobTypeId}`}
                  onClick={() => drillOutToTrailIndex(index)}
                >
                  {item.label}
                </button>
              )}
            </span>
          ))}
        </nav>
      ) : null}

      <GraphCoach surface="job_lifecycle" />

      {permissionHealth ? (
        <div
          className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-100"
          data-testid="job-lifecycle-permission-health"
          role="status"
        >
          {JOB_LIFECYCLE_PERMISSION_HEALTH_COPY}
        </div>
      ) : null}
      {error ? (
        <div
          className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          data-testid="job-lifecycle-error"
          role="alert"
        >
          {error}
        </div>
      ) : null}
      {dropHint ? (
        <div
          className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm text-muted-foreground"
          data-testid="job-lifecycle-drop-hint"
        >
          {dropHint}
        </div>
      ) : null}
      {conflict ? (
        <div
          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-100"
          data-testid="job-lifecycle-conflict-banner"
          role="alert"
        >
          <span>{conflict}</span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            data-testid="job-lifecycle-conflict-reload"
            onClick={reloadAfterConflict}
          >
            Reload pack
          </Button>
        </div>
      ) : null}
      {shouldShowBaselineBanner(viewingBaselineId) && baselineBanner ? (
        <div
          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-sm text-sky-950 dark:text-sky-100"
          data-testid="job-lifecycle-baseline-banner"
          role="status"
        >
          <span>{baselineBanner}</span>
          <div className="flex items-center gap-2">
            {baselineDiff ? (
              <span className="text-xs" data-testid="job-lifecycle-baseline-diff-summary">
                {summariseBaselineDiff(baselineDiff)}
              </span>
            ) : null}
            <Button
              type="button"
              size="sm"
              variant="outline"
              data-testid="job-lifecycle-baseline-clear"
              onClick={handleClearBaselineView}
            >
              Back to live tip
            </Button>
          </div>
        </div>
      ) : null}
      {readinessError ? (
        <div
          className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-100"
          data-testid="job-lifecycle-readiness-error"
          role="status"
        >
          Evidence readiness could not be loaded, so mandatory cells read as unknown rather than
          ready: {readinessError}
        </div>
      ) : null}
      {unreadyCount > 0 ? (
        <div
          className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          data-testid="job-lifecycle-readiness-summary"
          role="status"
        >
          {unreadyCount} mandatory-evidence cell(s) are not satisfied
          {freshnessOn ? ' (checked against Library / Document Control)' : ' (presence check only)'}.
        </div>
      ) : null}
      {freshnessOn && freshnessError ? (
        <div
          className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-100"
          data-testid="job-lifecycle-freshness-error"
          role="status"
        >
          Document status could not be loaded, so freshness reads as unknown rather than current:{' '}
          {freshnessError}
        </div>
      ) : null}

      <div
        className="grid gap-0"
        style={{
          gridTemplateColumns: `${panelWidths.left}px 6px minmax(0,1fr) 6px ${panelWidths.right}px`,
        }}
        data-testid="job-lifecycle-composer-grid"
      >
        <Card className="p-4 space-y-4 min-w-0" data-testid="job-lifecycle-axes">
          <div className="space-y-2">
            <h2 className="text-sm font-medium">Job cycles</h2>
            <p className="text-[11px] text-muted-foreground">
              A job cycle is a process pack (JobType) — pick or create one to author lanes and steps.
            </p>
            <label className="block space-y-1">
              <span className="text-[11px] text-muted-foreground">Active job cycle</span>
              <select
                className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                value={effectiveJobTypeId ?? ''}
                onChange={(e) => {
                  const next = Number(e.target.value)
                  setSelectedJobTypeId(Number.isFinite(next) && next > 0 ? next : null)
                }}
                data-testid="job-lifecycle-cycle-picker"
              >
                {orderedJobTypes.length === 0 ? (
                  <option value="">No job cycles yet</option>
                ) : null}
                {orderedJobTypes.map((jt) => (
                  <option key={jt.id} value={jt.id}>
                    {jt.name} ({jt.code})
                  </option>
                ))}
              </select>
            </label>
            <div className="flex gap-2">
              <Input
                value={newJobTypeName}
                onChange={(e) => setNewJobTypeName(e.target.value)}
                placeholder="New job cycle name"
                data-testid="job-lifecycle-new-type"
              />
              <Button
                type="button"
                size="sm"
                onClick={() => void handleCreateJobType()}
                disabled={saving || !newJobTypeName.trim()}
                data-testid="job-lifecycle-add-type"
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex gap-2">
              <Input
                value={cloneName}
                onChange={(e) => setCloneName(e.target.value)}
                placeholder="Clone axes as…"
                disabled={!effectiveJobTypeId}
                data-testid="job-lifecycle-clone-name"
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => void handleCloneJobType()}
                disabled={saving || !effectiveJobTypeId || !cloneName.trim()}
                data-testid="job-lifecycle-clone-type"
                title="Copy this pack's lanes and steps into a new job cycle. Cells stay empty — evidence belongs to the pack that earned it."
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Cloning copies lanes and steps only. Cells, links and document references are not
              copied — a reference asserts that <em>this</em> pack is evidenced by that document.
            </p>
            <div className="space-y-2 border-t border-border pt-3">
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Baselines
              </h3>
              <div className="flex gap-2">
                <Input
                  value={baselineLabel}
                  onChange={(e) => setBaselineLabel(e.target.value)}
                  placeholder="Baseline label (optional)"
                  disabled={!effectiveJobTypeId}
                  data-testid="job-lifecycle-baseline-label"
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => void handleCreateBaseline()}
                  disabled={saving || !effectiveJobTypeId}
                  data-testid="job-lifecycle-baseline-create"
                  title="Snapshot axes and nest edges at the live tip. Edit always stays on live."
                >
                  Snapshot
                </Button>
              </div>
              <ul className="space-y-1" data-testid="job-lifecycle-baseline-list">
                {baselines.length === 0 ? (
                  <li className="text-[11px] text-muted-foreground">No baselines yet.</li>
                ) : (
                  baselines.map((baseline) => (
                    <li key={baseline.id} className="flex items-center justify-between gap-2">
                      <button
                        type="button"
                        className={`flex-1 text-left rounded-md px-2 py-1 text-xs ${
                          viewingBaselineId === baseline.id
                            ? 'bg-sky-500/10 text-sky-900 dark:text-sky-100'
                            : 'hover:bg-muted/60'
                        }`}
                        data-testid={`job-lifecycle-baseline-${baseline.id}`}
                        onClick={() => void handleViewBaseline(baseline.id)}
                      >
                        {baseline.label?.trim() || `Baseline #${baseline.id}`}
                        <span className="ml-2 text-[10px] text-muted-foreground">
                          {new Date(baseline.created_at).toLocaleString()}
                        </span>
                      </button>
                    </li>
                  ))
                )}
              </ul>
              <p className="text-[11px] text-muted-foreground">
                Baselines are snapshots, not forks. Viewing one never redirects an edit onto the
                snapshot.
              </p>
            </div>
            <ul className="space-y-1" data-testid="job-lifecycle-type-list">
              {orderedJobTypes.map((jt) => (
                <li key={jt.id}>
                  <button
                    type="button"
                    className={`w-full text-left rounded-md px-2 py-1.5 text-sm ${
                      jt.id === effectiveJobTypeId
                        ? 'bg-primary/10 text-primary'
                        : 'hover:bg-muted/60'
                    }`}
                    data-testid={`job-lifecycle-type-${jt.id}`}
                    onClick={() => setSelectedJobTypeId(jt.id)}
                  >
                    {jt.name}
                    <span className="ml-2 text-[10px] uppercase text-muted-foreground">
                      {jt.code}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-2 border-t border-border pt-3">
            <h2 className="text-sm font-medium">Lanes</h2>
            <div className="flex gap-2">
              <Input
                value={newLaneName}
                onChange={(e) => setNewLaneName(e.target.value)}
                placeholder="New lane"
                disabled={!effectiveJobTypeId}
                data-testid="job-lifecycle-new-lane"
              />
              <Button
                type="button"
                size="sm"
                onClick={() => void handleCreateLane()}
                disabled={saving || !effectiveJobTypeId || !newLaneName.trim()}
                data-testid="job-lifecycle-add-lane"
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <ul className="space-y-1 text-sm" data-testid="job-lifecycle-lane-list">
              {orderedLanes.map((lane) => {
                const nestChips = deriveLaneNestChips(cells, lane.id, jobTypes)
                return (
                  <li key={lane.id} className="space-y-1 rounded-md border border-border px-2 py-1.5">
                    <div className="flex items-center gap-1">
                      <Input
                        defaultValue={lane.name}
                        aria-label={`Rename lane ${lane.name}`}
                        data-testid={`job-lifecycle-lane-name-${lane.id}`}
                        onBlur={(e) => {
                          if (e.target.value.trim() !== lane.name) {
                            void handleRenameLane(lane.id, e.target.value)
                          }
                        }}
                      />
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-foreground disabled:opacity-40"
                        aria-label={`Move lane ${lane.name} up`}
                        data-testid={`job-lifecycle-lane-up-${lane.id}`}
                        disabled={saving}
                        onClick={() => void handleReorderLane(lane.id, 'up')}
                      >
                        <ChevronUp className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-foreground disabled:opacity-40"
                        aria-label={`Move lane ${lane.name} down`}
                        data-testid={`job-lifecycle-lane-down-${lane.id}`}
                        disabled={saving}
                        onClick={() => void handleReorderLane(lane.id, 'down')}
                      >
                        <ChevronDown className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    {nestChips.length > 0 ? (
                      <div
                        className="flex flex-wrap gap-1"
                        data-testid={`job-lifecycle-lane-nest-${lane.id}`}
                      >
                        {nestChips.map((chip) => (
                          <button
                            key={chip.targetJobTypeId}
                            type="button"
                            className="inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] text-primary"
                            title="Nested job cycle — derived from job_cycle cell links"
                            data-testid={`job-lifecycle-lane-nest-chip-${lane.id}-${chip.targetJobTypeId}`}
                            onClick={() => drillIntoCycle(chip.targetJobTypeId)}
                          >
                            <GitBranch className="h-2.5 w-2.5" />
                            {chip.label}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          </div>

          <div className="space-y-2 border-t border-border pt-3">
            <h2 className="text-sm font-medium">Steps</h2>
            <div className="flex gap-2">
              <Input
                value={newStepName}
                onChange={(e) => setNewStepName(e.target.value)}
                placeholder="New step"
                disabled={!effectiveJobTypeId}
                data-testid="job-lifecycle-new-step"
              />
              <Button
                type="button"
                size="sm"
                onClick={() => void handleCreateStep()}
                disabled={saving || !effectiveJobTypeId || !newStepName.trim()}
                data-testid="job-lifecycle-add-step"
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <ul className="space-y-1" data-testid="job-lifecycle-step-list">
              {orderedSteps.map((step) => {
                const phase = resolvePdcaPhase(step.pdca_phase)
                return (
                  <li
                    key={step.id}
                    className={`space-y-1 rounded-md border px-2 py-1.5 ${
                      step.id === effectiveStepId ? 'border-primary/50' : 'border-border'
                    }`}
                  >
                    <div className="flex items-center gap-1">
                      <Input
                        defaultValue={step.name}
                        aria-label={`Rename step ${step.name}`}
                        data-testid={`job-lifecycle-step-name-${step.id}`}
                        onBlur={(e) => {
                          if (e.target.value.trim() !== step.name) {
                            void handleRenameStep(step.id, e.target.value)
                          }
                        }}
                      />
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-foreground disabled:opacity-40"
                        aria-label={`Move step ${step.name} up`}
                        data-testid={`job-lifecycle-step-up-${step.id}`}
                        disabled={saving}
                        onClick={() => void handleReorderStep(step.id, 'up')}
                      >
                        <ChevronUp className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-foreground disabled:opacity-40"
                        aria-label={`Move step ${step.name} down`}
                        data-testid={`job-lifecycle-step-down-${step.id}`}
                        disabled={saving}
                        onClick={() => void handleReorderStep(step.id, 'down')}
                      >
                        <ChevronDown className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        className={`flex-1 text-left rounded-md px-2 py-1 text-xs ${
                          step.id === effectiveStepId
                            ? 'bg-primary/10 text-primary'
                            : 'hover:bg-muted/60'
                        }`}
                        data-testid={`job-lifecycle-step-${step.id}`}
                        onClick={() => {
                          setSelectedStepId(step.id)
                          if (viewMode === 'phase') setMode('phase')
                        }}
                      >
                        Select
                      </button>
                      <button
                        type="button"
                        className={`rounded-full border px-2 py-0.5 text-[10px] ${pdcaPhaseClasses(phase)}`}
                        aria-label={`Cycle PDCA phase for ${step.name} (currently ${pdcaPhaseLabel(phase)})`}
                        data-testid={`job-lifecycle-step-pdca-${step.id}`}
                        disabled={saving}
                        onClick={() => void handleCyclePdcaPhase(step)}
                      >
                        {pdcaPhaseLabel(phase)}
                      </button>
                    </div>
                  </li>
                )
              })}
            </ul>
          </div>
        </Card>

        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize job cycle panel"
          data-testid="job-lifecycle-resize-left"
          className="cursor-col-resize bg-border/60 hover:bg-primary/40"
          onPointerDown={onPanelPointerDown.bind(null, 'left')}
          onPointerMove={onPanelPointerMove}
          onPointerUp={onPanelPointerUp}
          onPointerCancel={onPanelPointerUp}
        />

        {graphMode ? (
          <JobGraphPanel
            mode={viewMode === 'map' ? 'map' : 'trail'}
            jobTypeId={effectiveJobTypeId}
            assure={freshnessOn}
            refreshKey={derivedNonce}
            onDrillIntoCycle={drillIntoCycle}
          />
        ) : (
        <Card className="p-4 space-y-3 overflow-x-auto min-w-0" data-testid="job-lifecycle-matrix">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-8 justify-center">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading job lifecycle…
            </div>
          ) : axes.rows.length === 0 || axes.columns.length === 0 ? (
            <p className="text-sm text-muted-foreground py-8 text-center" data-testid="job-lifecycle-empty">
              {emptyComposerCopy(orderedJobTypes.length > 0)}
            </p>
          ) : (
            <table className="w-full border-collapse text-sm" data-testid="job-lifecycle-grid">
              <thead>
                <tr>
                  <th className="sticky left-0 bg-background border border-border p-2 text-left text-xs font-medium text-muted-foreground">
                    {axes.rowAxis === 'lane' ? 'Lane \\ Step' : 'Step \\ Lane'}
                  </th>
                  {axes.columns.map((col) => (
                    <th
                      key={col.id}
                      className={`border p-2 text-left font-medium min-w-[140px] ${
                        axisHeaderPdcaClasses(col, axes.columnAxis) || 'border-border'
                      }`}
                      data-testid={`job-lifecycle-col-${col.id}`}
                      data-pdca-phase={
                        axes.columnAxis === 'step'
                          ? resolvePdcaPhase((col as { pdca_phase?: unknown }).pdca_phase) ?? 'none'
                          : undefined
                      }
                    >
                      <span>{col.name}</span>
                      {axes.columnAxis === 'step' ? (
                        <span className="ml-1 text-[10px] uppercase opacity-70">
                          {axisPdcaLabel(col, axes.columnAxis)}
                        </span>
                      ) : null}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {axes.rows.map((row) => (
                  <tr key={row.id}>
                    <th
                      className={`sticky left-0 border p-2 text-left font-medium ${
                        axisHeaderPdcaClasses(row, axes.rowAxis) || 'bg-background border-border'
                      }`}
                      data-testid={`job-lifecycle-row-${row.id}`}
                      data-pdca-phase={
                        axes.rowAxis === 'step'
                          ? resolvePdcaPhase((row as { pdca_phase?: unknown }).pdca_phase) ?? 'none'
                          : undefined
                      }
                    >
                      {row.name}
                    </th>
                    {axes.columns.map((col) => {
                      const { laneId, stepId } = cellLaneStep(row, col)
                      const docs =
                        cellIndex.get(cellKey(laneId, stepId))?.library_document_ids ?? []
                      const selected =
                        selectedLaneId === laneId && selectedStepId === stepId
                      const required = Boolean(
                        cellIndex.get(cellKey(laneId, stepId))?.requires_evidence,
                      )
                      const verdict = readinessIndex.get(cellKey(laneId, stepId)) ?? null
                      return (
                        <td
                          key={`${laneId}:${stepId}`}
                          className={`border border-border align-top p-2 min-h-[88px] ${
                            selected ? 'bg-primary/5' : 'bg-muted/10'
                          }`}
                          data-testid={`job-lifecycle-cell-${laneId}-${stepId}`}
                          onDragOver={(e) => {
                            e.preventDefault()
                            e.dataTransfer.dropEffect = 'copy'
                          }}
                          onDrop={(e) => void onCellDrop(e, laneId, stepId)}
                          onClick={() => {
                            setSelectedLaneId(laneId)
                            setSelectedStepId(stepId)
                          }}
                        >
                          <div className="mb-1 flex items-center justify-between gap-1">
                            <button
                              type="button"
                              className={`rounded-full border px-1.5 py-0 text-[9px] uppercase tracking-wide ${
                                required
                                  ? 'border-primary/40 bg-primary/10 text-primary'
                                  : 'border-border bg-muted/30 text-muted-foreground'
                              }`}
                              aria-pressed={required}
                              aria-label={`${required ? 'Clear' : 'Set'} mandatory evidence for ${row.name} × ${col.name}`}
                              data-testid={`job-lifecycle-cell-requirement-${laneId}-${stepId}`}
                              data-requires-evidence={required ? 'true' : 'false'}
                              disabled={saving}
                              title={
                                required
                                  ? 'This cell must hold evidence. Readiness is derived from its document refs.'
                                  : 'Mark this cell as owing evidence.'
                              }
                              onClick={(e) => {
                                e.stopPropagation()
                                void handleToggleCellRequirement(laneId, stepId)
                              }}
                            >
                              {required ? 'Evidence required' : 'Optional'}
                            </button>
                            {required && verdict ? (
                              <span
                                className={`shrink-0 rounded-full border px-1.5 py-0 text-[9px] uppercase tracking-wide ${readinessStateClasses(verdict.state)}`}
                                data-testid={`job-lifecycle-cell-readiness-${laneId}-${stepId}`}
                                data-readiness-state={verdict.state}
                                title={readinessTitle(verdict)}
                              >
                                {readinessStateLabel(verdict.state)}
                              </span>
                            ) : null}
                          </div>
                          <div className="space-y-1 min-h-[72px]">
                            {docs.length === 0 ? (
                              <p className="text-[11px] text-muted-foreground">
                                Drop library docs (refs)
                              </p>
                            ) : (
                              docs.map((docId) => (
                                <div
                                  key={docId}
                                  className="flex items-center gap-1 rounded border border-border bg-background px-1.5 py-0.5"
                                  data-testid={`job-lifecycle-cell-doc-${laneId}-${stepId}-${docId}`}
                                >
                                  <Link
                                    to={`/documents/${docId}`}
                                    className="flex-1 truncate text-xs hover:underline"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    {libraryDocLabel(docsById, docId)}
                                  </Link>
                                  {renderFreshnessChip(
                                    docId,
                                    `job-lifecycle-cell-doc-freshness-${laneId}-${stepId}-${docId}`,
                                  )}
                                  <button
                                    type="button"
                                    className="text-muted-foreground hover:text-destructive"
                                    aria-label={`Remove document ${docId} reference`}
                                    data-testid={`job-lifecycle-remove-doc-${laneId}-${stepId}-${docId}`}
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      void removeDocFromCell(laneId, stepId, docId)
                                    }}
                                  >
                                    <Trash2 className="h-3 w-3" />
                                  </button>
                                </div>
                              ))
                            )}
                            {jobCellLinksEnabled
                              ? (
                                  cellIndex.get(cellKey(laneId, stepId))?.links ?? []
                                ).map((link) =>
                                  link.kind === 'job_cycle' && link.target_job_type_id ? (
                                    <button
                                      key={`link-${link.id}`}
                                      type="button"
                                      className="flex w-full items-center gap-1 truncate rounded border border-primary/40 bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary"
                                      data-testid={`job-lifecycle-cell-nest-${laneId}-${stepId}-${link.id}`}
                                      title={`Drill into nested job cycle — ${link.href}`}
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        drillIntoCycle(Number(link.target_job_type_id))
                                      }}
                                    >
                                      <GitBranch className="h-2.5 w-2.5 shrink-0" />
                                      <span className="truncate">{link.label}</span>
                                    </button>
                                  ) : (
                                    <div
                                      key={`link-${link.id}`}
                                      className="flex items-center gap-1 rounded border border-dashed border-border px-1.5 py-0.5 text-[10px] text-muted-foreground"
                                      data-testid={`job-lifecycle-cell-link-${laneId}-${stepId}-${link.id}`}
                                      title={link.href}
                                    >
                                      <span className="truncate">
                                        {link.kind}: {link.label}
                                      </span>
                                      {link.kind === 'audit_outcome' ? (
                                        <span
                                          className={`shrink-0 rounded-full border px-1.5 py-0 text-[9px] uppercase tracking-wide ${auditLapseClasses(
                                            link.audit_lapse?.state ?? 'unknown',
                                          )}`}
                                          data-testid={`job-lifecycle-cell-lapse-${laneId}-${stepId}-${link.id}`}
                                          data-lapse-state={link.audit_lapse?.state ?? 'unknown'}
                                          title={auditLapseTitle(link.audit_lapse)}
                                        >
                                          {auditLapseLabel(link.audit_lapse?.state ?? 'unknown')}
                                        </span>
                                      ) : null}
                                    </div>
                                  ),
                                )
                              : null}
                          </div>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        )}

        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize library panel"
          data-testid="job-lifecycle-resize-right"
          className="cursor-col-resize bg-border/60 hover:bg-primary/40"
          onPointerDown={onPanelPointerDown.bind(null, 'right')}
          onPointerMove={onPanelPointerMove}
          onPointerUp={onPanelPointerUp}
          onPointerCancel={onPanelPointerUp}
        />

        <div className="space-y-4 min-w-0">
          <Card className="p-4 space-y-3" data-testid="job-lifecycle-library-tray">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-medium">Library tray</h2>
              {!libraryDragEnabled ? (
                <Badge variant="outline" className="text-[10px]">
                  DnD flag off
                </Badge>
              ) : null}
            </div>
            <Input
              value={libraryFilter}
              onChange={(e) => setLibraryFilter(e.target.value)}
              placeholder="Filter library…"
              data-testid="job-lifecycle-library-filter"
            />
            <ul className="max-h-[320px] space-y-1 overflow-y-auto" data-testid="job-lifecycle-library-list">
              {filteredLibrary.map((doc) => (
                <li key={doc.id}>
                  {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions -- HTML5 library DnD is mouse-only; attach also available via cell drop from Documents tray */}
                  <div
                    className={`rounded-md border border-border px-2 py-1.5 text-xs ${
                      libraryDragEnabled ? 'cursor-grab active:cursor-grabbing' : ''
                    }`}
                    draggable={libraryDragEnabled}
                    onDragStart={(e) => onLibraryDragStart(e, doc)}
                    data-testid={`job-lifecycle-library-doc-${doc.id}`}
                    title={
                      libraryDragEnabled
                        ? 'Drag onto a cell to attach a document reference'
                        : 'Enable document_graph_dnd_propose to drag'
                    }
                  >
                    <div className="flex items-center gap-1">
                      <span className="font-medium truncate">{doc.title}</span>
                      {renderFreshnessChip(doc.id, `job-lifecycle-library-freshness-${doc.id}`)}
                    </div>
                    {doc.reference ? (
                      <div className="text-muted-foreground truncate">{doc.reference}</div>
                    ) : null}
                  </div>
                </li>
              ))}
              {filteredLibrary.length === 0 ? (
                <li className="text-xs text-muted-foreground py-2">No library documents.</li>
              ) : null}
            </ul>
            {libraryPage < libraryPages ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="w-full"
                disabled={libraryLoadingMore}
                onClick={() => void loadMoreLibrary()}
                data-testid="job-lifecycle-library-more"
              >
                {libraryLoadingMore ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  'Load more library docs'
                )}
              </Button>
            ) : null}
            <p className="text-[11px] text-muted-foreground">
              Drop attaches <code>library_document_id</code> only — document bodies stay in the
              library SSOT. Tray loads pages lazily to protect rate limits.
            </p>
          </Card>

          {effectiveStepId != null ? (
            <div data-testid="job-lifecycle-connections">
              <Entity360Strip entityType="job_step" entityId={effectiveStepId} />
            </div>
          ) : (
            <Card className="p-4 text-sm text-muted-foreground" data-testid="job-lifecycle-connections-empty">
              Select a step to load Connections (Entity360).
            </Card>
          )}

          {selectedJobTypeId != null && selectedLaneId != null && selectedStepId != null ? (
            <JobCellLinks
              jobTypeId={selectedJobTypeId}
              laneId={selectedLaneId}
              stepId={selectedStepId}
              jobLifecycleEnabled={jobLifecycleEnabled}
              jobCellLinksEnabled={jobCellLinksEnabled}
              initialLinks={selectedCellLinks}
              onLinksChange={handleLinksChange}
              jobTypes={orderedJobTypes}
            />
          ) : null}
        </div>
      </div>

    </div>
  )
}
