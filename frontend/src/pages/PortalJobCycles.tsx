/**
 * Portal nested-cycle read (JL-UX-W5 #8).
 *
 * Field users open a job cycle read-only — nest drill reuses the same
 * `job_cycle` / cycle-graph SSOT as the composer. No author chrome, no PATCH.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, GitBranch, Loader2, Layers } from 'lucide-react'
import { getApiErrorMessage, jobLifecycleApi } from '../api/client'
import type { PortalNestedCycleResponse } from '../api/jobLifecycleClient'
import { Card } from '../components/ui/Card'
import { useFeatureFlag } from '../hooks/useFeatureFlag'
import {
  portalCycleIsReadOnly,
  portalNestTargets,
  pushDrillTrail,
  shouldShowJobCycleBreadcrumb,
  sortAxesByOrder,
  truncateDrillTrail,
} from './jobLifecycleHelpers'

export default function PortalJobCycles() {
  const navigate = useNavigate()
  const params = useParams<{ jobTypeId?: string }>()
  const jobLifecycleEnabled = useFeatureFlag('job_lifecycle')

  const routeJobTypeId = params.jobTypeId ? Number(params.jobTypeId) : null
  const [selectedId, setSelectedId] = useState<number | null>(
    Number.isFinite(routeJobTypeId) ? routeJobTypeId : null,
  )
  const [drillTrail, setDrillTrail] = useState<number[]>([])
  const [payload, setPayload] = useState<PortalNestedCycleResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [catalog, setCatalog] = useState<Array<{ id: number; name: string; code: string }>>([])

  const effectiveId = selectedId

  const loadCatalog = useCallback(async () => {
    if (!jobLifecycleEnabled) return
    try {
      const res = await jobLifecycleApi.portalListJobTypes()
      setCatalog(
        (res.data.items ?? []).map((jt) => ({ id: jt.id, name: jt.name, code: jt.code })),
      )
      if (selectedId == null && res.data.items?.[0]) {
        setSelectedId(res.data.items[0].id)
      }
    } catch (err) {
      setError(getApiErrorMessage(err) || 'Could not load job cycles.')
    }
  }, [jobLifecycleEnabled, selectedId])

  const loadCycle = useCallback(async (jobTypeId: number) => {
    setLoading(true)
    setError(null)
    try {
      const res = await jobLifecycleApi.portalNestedCycle(jobTypeId)
      setPayload(res.data)
      if (!portalCycleIsReadOnly(res.data)) {
        setError('Portal cycle response was not read-only — refusing to render author chrome.')
        setPayload(null)
      }
    } catch (err) {
      setPayload(null)
      setError(getApiErrorMessage(err) || 'Could not load this job cycle.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadCatalog()
  }, [loadCatalog])

  useEffect(() => {
    if (!jobLifecycleEnabled || effectiveId == null) {
      setLoading(false)
      return
    }
    void loadCycle(effectiveId)
  }, [effectiveId, jobLifecycleEnabled, loadCycle])

  const lanes = useMemo(
    () => sortAxesByOrder(payload?.lanes ?? []),
    [payload?.lanes],
  )
  const steps = useMemo(
    () => sortAxesByOrder(payload?.steps ?? []),
    [payload?.steps],
  )
  const nests = useMemo(() => portalNestTargets(payload?.cells), [payload?.cells])

  const cellAt = (laneId: number, stepId: number) =>
    (payload?.cells ?? []).find((cell) => cell.lane_id === laneId && cell.step_id === stepId)

  const drillInto = (targetId: number) => {
    if (effectiveId != null) {
      setDrillTrail((prev) => pushDrillTrail(prev, effectiveId))
    }
    setSelectedId(targetId)
    navigate(`/portal/job-cycles/${targetId}`)
  }

  const drillOutTo = (index: number) => {
    const ancestor = drillTrail[index]
    if (ancestor == null) return
    setDrillTrail((prev) => truncateDrillTrail(prev, index))
    setSelectedId(ancestor)
    navigate(`/portal/job-cycles/${ancestor}`)
  }

  if (!jobLifecycleEnabled) {
    return (
      <div data-testid="portal-job-cycles" className="min-h-screen bg-surface">
        <main className="max-w-lg mx-auto px-4 py-10">
          <Card className="p-6 text-center">
            <p className="text-sm text-muted-foreground">Job cycles are not available here.</p>
          </Card>
        </main>
      </div>
    )
  }

  return (
    <div data-testid="portal-job-cycles" className="min-h-screen bg-surface">
      <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate('/portal')}
            className="p-2 hover:bg-surface rounded-lg"
            aria-label="Back to portal home"
          >
            <ArrowLeft className="w-5 h-5 text-muted-foreground" />
          </button>
          <div>
            <h1 className="text-foreground font-semibold">Job cycles</h1>
            <p className="text-muted-foreground text-xs">Read-only nested process packs</p>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 space-y-4">
        <p
          className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground"
          data-testid="portal-job-cycles-readonly-banner"
        >
          Read only — you can open nested cycles and see attached documents, but you cannot edit
          the pack from the portal.
        </p>

        {catalog.length > 0 ? (
          <label className="block text-sm">
            <span className="text-muted-foreground text-xs">Job cycle</span>
            <select
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={effectiveId ?? ''}
              onChange={(e) => {
                const next = Number(e.target.value)
                setDrillTrail([])
                setSelectedId(next)
                navigate(`/portal/job-cycles/${next}`)
              }}
              data-testid="portal-job-cycles-picker"
            >
              {catalog.map((jt) => (
                <option key={jt.id} value={jt.id}>
                  {jt.name} ({jt.code})
                </option>
              ))}
            </select>
          </label>
        ) : null}

        {shouldShowJobCycleBreadcrumb(drillTrail) ? (
          <nav
            className="flex flex-wrap items-center gap-1 text-xs"
            data-testid="portal-job-cycles-breadcrumb"
            aria-label="Nested cycle path"
          >
            {drillTrail.map((id, index) => {
              const label = catalog.find((c) => c.id === id)?.name ?? `Cycle #${id}`
              return (
                <button
                  key={`${id}-${index}`}
                  type="button"
                  className="rounded px-1.5 py-0.5 text-primary hover:underline"
                  onClick={() => drillOutTo(index)}
                >
                  {label}
                </button>
              )
            })}
            <span className="text-muted-foreground">/</span>
            <span className="font-medium">{payload?.job_type.name ?? '…'}</span>
          </nav>
        ) : null}

        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
          </div>
        ) : null}

        {error ? (
          <Card className="p-4 border-destructive/30 bg-destructive/5" data-testid="portal-job-cycles-error">
            <p className="text-sm text-destructive">{error}</p>
          </Card>
        ) : null}

        {!loading && !error && payload ? (
          <>
            <Card className="p-4 space-y-2" data-testid="portal-job-cycles-summary">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-primary" />
                <h2 className="font-semibold text-foreground">{payload.job_type.name}</h2>
              </div>
              <p className="text-xs text-muted-foreground">
                {lanes.length} lane(s) · {steps.length} step(s) · {nests.length} nested cycle(s)
              </p>
            </Card>

            {nests.length > 0 ? (
              <Card className="p-4 space-y-2" data-testid="portal-job-cycles-nests">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <GitBranch className="w-4 h-4" />
                  Nested cycles
                </div>
                <ul className="space-y-1">
                  {nests.map((nest) => (
                    <li key={`${nest.cellId}-${nest.targetJobTypeId}`}>
                      <button
                        type="button"
                        className="w-full text-left rounded-md border border-border px-3 py-2 text-sm hover:bg-muted/50"
                        data-testid={`portal-job-cycles-nest-${nest.targetJobTypeId}`}
                        onClick={() => drillInto(nest.targetJobTypeId)}
                      >
                        {nest.label}
                      </button>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : null}

            <div className="overflow-x-auto" data-testid="portal-job-cycles-matrix">
              <table className="w-full min-w-[28rem] border-collapse text-xs">
                <thead>
                  <tr>
                    <th className="border border-border bg-muted/40 p-2 text-left">Lane</th>
                    {steps.map((step) => (
                      <th key={step.id} className="border border-border bg-muted/40 p-2 text-left">
                        {step.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {lanes.map((lane) => (
                    <tr key={lane.id}>
                      <th className="border border-border bg-muted/20 p-2 text-left font-medium">
                        {lane.name}
                      </th>
                      {steps.map((step) => {
                        const cell = cellAt(lane.id, step.id)
                        const docs = cell?.library_document_ids ?? []
                        const cellNests = cell?.nest_links ?? []
                        return (
                          <td
                            key={step.id}
                            className="border border-border p-2 align-top"
                            data-testid={`portal-job-cycles-cell-${lane.id}-${step.id}`}
                          >
                            {docs.length > 0 ? (
                              <span className="text-muted-foreground">{docs.length} doc(s)</span>
                            ) : (
                              <span className="text-muted-foreground/60">—</span>
                            )}
                            {cellNests.map((link) =>
                              typeof link.target_job_type_id === 'number' ? (
                                <button
                                  key={link.id}
                                  type="button"
                                  className="mt-1 block text-[10px] text-primary underline"
                                  onClick={() => drillInto(link.target_job_type_id as number)}
                                >
                                  {link.label}
                                </button>
                              ) : null,
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </main>
    </div>
  )
}
