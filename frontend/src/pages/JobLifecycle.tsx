/**
 * Job Lifecycle swimlane composer (JL-2 / ADR-0022).
 *
 * Flag-gated by `job_lifecycle` (default OFF). Matrix · Transpose · Phase are
 * views over the same JL-1 cells. Library DnD attaches document ID refs only.
 * Connections reuse Entity360 (X-1); coach reuses GraphCoach surface
 * `job_lifecycle` (X-2). Never invents a second document SSOT or org chart.
 */
import { useCallback, useEffect, useMemo, useState, type DragEvent } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { GitBranch, Loader2, Plus, Trash2 } from 'lucide-react'
import api, { getApiErrorMessage, jobLifecycleApi } from '../api/client'
import type { JobCell, JobLane, JobStep, JobType } from '../api/jobLifecycleClient'
import { useFeatureFlag } from '../hooks/useFeatureFlag'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
import { Entity360Strip, GraphCoach } from '../components/graph'
import JobCellLinks from '../components/jobLifecycle/JobCellLinks'
import {
  parseLibraryDocumentDrag,
  setLibraryDocumentDragData,
  shouldEnableLibraryDocumentDrag,
} from '../components/graph/documentGraphDndHelpers'
import {
  DEFAULT_JOB_LIFECYCLE_VIEW_MODE,
  buildAxisCode,
  buildCellIndex,
  cellKey,
  detachDocumentRef,
  emptyComposerCopy,
  jobLifecycleViewModeLabel,
  libraryDocLabel,
  readStoredJobLifecycleViewMode,
  resolveDndCellAttach,
  resolveJobLifecycleViewMode,
  resolveSelectedJobTypeId,
  resolveSelectedStepId,
  resolveSwimlaneAxes,
  shouldFetchJobLifecycle,
  shouldShowJobLifecycle,
  sortAxesByOrder,
  writeStoredJobLifecycleViewMode,
  type JobLifecycleLibraryDoc,
  type JobLifecycleViewMode,
} from './jobLifecycleHelpers'

interface LibraryDocumentPage {
  items?: Array<{
    id: number
    title: string
    reference_number?: string | null
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

  const { stepId: stepIdParam } = useParams<{ stepId?: string }>()
  const preferredStepId = useMemo(() => {
    const n = Number(stepIdParam)
    return Number.isFinite(n) && n > 0 ? n : null
  }, [stepIdParam])

  const [jobTypes, setJobTypes] = useState<JobType[]>([])
  const [lanes, setLanes] = useState<JobLane[]>([])
  const [steps, setSteps] = useState<JobStep[]>([])
  const [cells, setCells] = useState<JobCell[]>([])
  const [libraryDocs, setLibraryDocs] = useState<JobLifecycleLibraryDoc[]>([])
  const [selectedJobTypeId, setSelectedJobTypeId] = useState<number | null>(null)
  const [selectedStepId, setSelectedStepId] = useState<number | null>(preferredStepId)
  const [selectedLaneId, setSelectedLaneId] = useState<number | null>(null)
  const [viewMode, setViewMode] = useState<JobLifecycleViewMode>(() =>
    resolveJobLifecycleViewMode(readStoredJobLifecycleViewMode(), DEFAULT_JOB_LIFECYCLE_VIEW_MODE),
  )
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dropHint, setDropHint] = useState<string | null>(null)
  const [newJobTypeName, setNewJobTypeName] = useState('')
  const [newLaneName, setNewLaneName] = useState('')
  const [newStepName, setNewStepName] = useState('')
  const [libraryFilter, setLibraryFilter] = useState('')

  const cellIndex = useMemo(() => buildCellIndex(cells), [cells])
  const docsById = useMemo(() => {
    const map = new Map<number, JobLifecycleLibraryDoc>()
    for (const doc of libraryDocs) map.set(doc.id, doc)
    return map
  }, [libraryDocs])

  const orderedJobTypes = useMemo(() => sortAxesByOrder(jobTypes), [jobTypes])
  const orderedLanes = useMemo(() => sortAxesByOrder(lanes), [lanes])
  const orderedSteps = useMemo(() => sortAxesByOrder(steps), [steps])

  const effectiveJobTypeId = useMemo(
    () => resolveSelectedJobTypeId(selectedJobTypeId, jobTypes),
    [selectedJobTypeId, jobTypes],
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

  const loadPack = useCallback(async () => {
    if (!shouldFetch) {
      setJobTypes([])
      setLanes([])
      setSteps([])
      setCells([])
      setLibraryDocs([])
      setError(null)
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const [typesRes, libraryRes] = await Promise.all([
        jobLifecycleApi.listJobTypes(),
        (async () => {
          const pageSize = 100
          const collected: JobLifecycleLibraryDoc[] = []
          let page = 1
          let pages = 1
          while (page <= pages) {
            const res = await api.get<LibraryDocumentPage>(
              `/api/v1/documents/?page=${page}&page_size=${pageSize}`,
            )
            const items = res.data.items ?? []
            for (const item of items) {
              collected.push({
                id: item.id,
                title: item.title,
                reference: item.reference_number ?? null,
              })
            }
            pages = res.data.pages ?? 1
            page += 1
            if (items.length === 0) break
          }
          return collected
        })(),
      ])
      setJobTypes(typesRes.data.items ?? [])
      setLibraryDocs(libraryRes)
    } catch (err) {
      setJobTypes([])
      setLibraryDocs([])
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [shouldFetch])

  const loadAxesForType = useCallback(
    async (jobTypeId: number) => {
      if (!shouldFetch || !jobTypeId) {
        setLanes([])
        setSteps([])
        setCells([])
        return
      }
      setLoading(true)
      setError(null)
      try {
        const [lanesRes, stepsRes, cellsRes] = await Promise.all([
          jobLifecycleApi.listLanes(jobTypeId),
          jobLifecycleApi.listSteps(jobTypeId),
          jobLifecycleApi.listCells(jobTypeId),
        ])
        setLanes(lanesRes.data.items ?? [])
        setSteps(stepsRes.data.items ?? [])
        setCells(cellsRes.data.items ?? [])
      } catch (err) {
        setLanes([])
        setSteps([])
        setCells([])
        setError(getApiErrorMessage(err))
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

  useEffect(() => {
    if (preferredStepId != null) {
      setSelectedStepId(preferredStepId)
      setViewMode('phase')
    }
  }, [preferredStepId])

  if (!visible) {
    return <Navigate to="/documents" replace />
  }

  const setMode = (next: JobLifecycleViewMode) => {
    setViewMode(next)
    writeStoredJobLifecycleViewMode(next)
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
            Compose swimlanes from JL process axes (job type · lane · step). Cells hold library
            document references only — never a second document store, never an org chart.
          </p>
        </div>
        <div
          className="inline-flex rounded-md border border-border p-0.5"
          role="group"
          aria-label="Swimlane view mode"
          data-testid="job-lifecycle-view-mode"
        >
          {(['matrix', 'transpose', 'phase'] as const).map((mode) => (
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
      </div>

      <GraphCoach surface="job_lifecycle" />

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

      <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)_260px]">
        <Card className="p-4 space-y-4" data-testid="job-lifecycle-axes">
          <div className="space-y-2">
            <h2 className="text-sm font-medium">Job types</h2>
            <div className="flex gap-2">
              <Input
                value={newJobTypeName}
                onChange={(e) => setNewJobTypeName(e.target.value)}
                placeholder="New job type"
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
              {orderedLanes.map((lane) => (
                <li key={lane.id} className="px-2 py-1 text-muted-foreground">
                  {lane.name}
                </li>
              ))}
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
              {orderedSteps.map((step) => (
                <li key={step.id}>
                  <button
                    type="button"
                    className={`w-full text-left rounded-md px-2 py-1.5 text-sm ${
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
                    {step.name}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </Card>

        <Card className="p-4 space-y-3 overflow-x-auto" data-testid="job-lifecycle-matrix">
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
                      className="border border-border p-2 text-left font-medium min-w-[140px]"
                      data-testid={`job-lifecycle-col-${col.id}`}
                    >
                      {col.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {axes.rows.map((row) => (
                  <tr key={row.id}>
                    <th
                      className="sticky left-0 bg-background border border-border p-2 text-left font-medium"
                      data-testid={`job-lifecycle-row-${row.id}`}
                    >
                      {row.name}
                    </th>
                    {axes.columns.map((col) => {
                      const { laneId, stepId } = cellLaneStep(row, col)
                      const docs =
                        cellIndex.get(cellKey(laneId, stepId))?.library_document_ids ?? []
                      const selected =
                        selectedLaneId === laneId && selectedStepId === stepId
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
                                ).map((link) => (
                                  <div
                                    key={`link-${link.id}`}
                                    className="truncate rounded border border-dashed border-border px-1.5 py-0.5 text-[10px] text-muted-foreground"
                                    data-testid={`job-lifecycle-cell-link-${laneId}-${stepId}-${link.id}`}
                                    title={link.href}
                                  >
                                    {link.kind}: {link.label}
                                  </div>
                                ))
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

        <div className="space-y-4">
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
                    <div className="font-medium truncate">{doc.title}</div>
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
            <p className="text-[11px] text-muted-foreground">
              Drop attaches <code>library_document_id</code> only — document bodies stay in the
              library SSOT.
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
              initialLinks={
                cellIndex.get(cellKey(selectedLaneId, selectedStepId))?.links ?? []
              }
            />
          ) : null}
        </div>
      </div>
    </div>
  )
}
