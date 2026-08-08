/**
 * JobGraphPanel — JL-UX-W4 Map and Trail, over one shared edge model.
 *
 * Map answers "what does this pack interact with", from `job_cycle` cell links.
 * Trail answers "walk me one path", from the same node/edge vocabulary plus the
 * cells' own document refs and links.
 *
 * Both are **views**. Nothing here writes, and every line on screen is a row
 * that already exists in `job_cell_links` or `job_cell_documents` — delete the
 * link in the composer and the line goes with it. Hrefs come from the server's
 * href_registry, never from a second URL builder in the client.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { GitBranch, Loader2, RefreshCw } from 'lucide-react'
import { getApiErrorMessage, jobLifecycleApi } from '../../api/client'
import type {
  JobAuditTrailResponse,
  JobCycleGraphResponse,
  JobGraphEdge,
  JobGraphNode,
} from '../../api/jobLifecycleClient'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import {
  buildGraphNodeIndex,
  edgesFromNode,
  graphEdgeKindLabel,
  graphNodeKindLabel,
  graphNodeLinkTarget,
  isForbiddenApiError,
  JOB_LIFECYCLE_PERMISSION_HEALTH_COPY,
  layoutJobGraph,
  readinessStateClasses,
  readinessStateLabel,
  readinessTitle,
  resolveTrailPathNodes,
} from '../../pages/jobLifecycleHelpers'

export interface JobGraphPanelProps {
  mode: 'map' | 'trail'
  jobTypeId: number | null
  /** Trail assurance follows the composer's Freshness toggle. */
  assure: boolean
  /** Bumped by the parent after a write, to re-read the view. */
  refreshKey?: number
  onDrillIntoCycle?: (jobTypeId: number) => void
}

/** Internal node chip. A node with an href is navigable; one without is not. */
function GraphNodeChip({
  node,
  onDrillIntoCycle,
}: {
  node: JobGraphNode
  onDrillIntoCycle?: (jobTypeId: number) => void
}) {
  const unavailable = node.detail === 'unavailable'
  const className = `inline-flex max-w-full items-center gap-1 rounded-md border px-2 py-1 text-xs ${
    unavailable
      ? 'border-dashed border-destructive/40 bg-destructive/5 text-destructive'
      : 'border-border bg-background'
  }`
  const body = (
    <>
      <span className="shrink-0 text-[9px] uppercase tracking-wide text-muted-foreground">
        {graphNodeKindLabel(node.kind)}
      </span>
      <span className="truncate">{node.label}</span>
      {unavailable ? <span className="shrink-0 text-[9px] uppercase">gone</span> : null}
    </>
  )

  if (node.kind === 'job_type' && onDrillIntoCycle && !unavailable) {
    return (
      <button
        type="button"
        className={className}
        data-testid={`job-graph-node-${node.key}`}
        data-node-kind={node.kind}
        title={`Open job cycle — ${node.href ?? 'no link'}`}
        onClick={() => onDrillIntoCycle(node.ref_id)}
      >
        {body}
      </button>
    )
  }

  const linkTarget = graphNodeLinkTarget(node)
  if (linkTarget === 'internal') {
    return (
      <Link
        to={node.href as string}
        className={`${className} hover:underline`}
        data-testid={`job-graph-node-${node.key}`}
        data-node-kind={node.kind}
        title={node.href ?? undefined}
      >
        {body}
      </Link>
    )
  }
  if (linkTarget === 'external') {
    return (
      <a
        href={node.href as string}
        target="_blank"
        rel="noopener noreferrer"
        className={`${className} hover:underline`}
        data-testid={`job-graph-node-${node.key}`}
        data-node-kind={node.kind}
        title={node.href ?? undefined}
      >
        {body}
      </a>
    )
  }

  return (
    <span
      className={className}
      data-testid={`job-graph-node-${node.key}`}
      data-node-kind={node.kind}
      title={unavailable ? 'This target is no longer available' : node.label}
    >
      {body}
    </span>
  )
}

function GraphEdgeRow({ edge }: { edge: JobGraphEdge }) {
  return (
    <li
      className="flex items-center gap-1 text-[11px] text-muted-foreground"
      data-testid={`job-graph-edge-${edge.key}`}
      data-edge-kind={edge.kind}
    >
      <GitBranch className="h-3 w-3 shrink-0 opacity-60" />
      <span className="shrink-0 uppercase tracking-wide">{graphEdgeKindLabel(edge.kind)}</span>
      <span className="truncate">{edge.label}</span>
    </li>
  )
}

export default function JobGraphPanel({
  mode,
  jobTypeId,
  assure,
  refreshKey = 0,
  onDrillIntoCycle,
}: JobGraphPanelProps) {
  const [graph, setGraph] = useState<JobCycleGraphResponse | null>(null)
  const [trail, setTrail] = useState<JobAuditTrailResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    if (jobTypeId == null) {
      setGraph(null)
      setTrail(null)
      setError(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    void (async () => {
      try {
        if (mode === 'map') {
          const res = await jobLifecycleApi.getCycleGraph(jobTypeId)
          if (cancelled) return
          setGraph(res.data)
          setTrail(null)
        } else {
          const res = await jobLifecycleApi.getAuditTrail(jobTypeId, { assure })
          if (cancelled) return
          setTrail(res.data)
          setGraph(null)
        }
      } catch (err) {
        if (cancelled) return
        setGraph(null)
        setTrail(null)
        setError(
          isForbiddenApiError(err) ? JOB_LIFECYCLE_PERMISSION_HEALTH_COPY : getApiErrorMessage(err),
        )
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [mode, jobTypeId, assure, refreshKey, reloadKey])

  const heading = mode === 'map' ? 'Process interaction map' : 'Audit trail'
  const blurb =
    mode === 'map'
      ? 'Every line is one job_cycle cell link. This is a view of those links, not a second place they are recorded.'
      : 'A sample walk from the pack to the evidence behind it. Sampled, not an export — the count below says how many paths exist.'

  return (
    <Card className="p-4 space-y-3 min-w-0 overflow-x-auto" data-testid={`job-graph-panel-${mode}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <h2 className="text-sm font-medium">{heading}</h2>
          <p className="max-w-2xl text-[11px] text-muted-foreground">{blurb}</p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={loading || jobTypeId == null}
          data-testid={`job-graph-refresh-${mode}`}
          onClick={() => setReloadKey((k) => k + 1)}
        >
          {loading ? (
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="mr-1 h-3.5 w-3.5" />
          )}
          Refresh
        </Button>
      </div>

      {error ? (
        <div
          className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          data-testid={`job-graph-error-${mode}`}
          role="alert"
        >
          {error}
        </div>
      ) : null}

      {jobTypeId == null ? (
        <p className="py-6 text-center text-sm text-muted-foreground" data-testid="job-graph-no-cycle">
          Select a job cycle to read it as a graph.
        </p>
      ) : loading ? (
        <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading {heading.toLowerCase()}…
        </div>
      ) : mode === 'map' ? (
        <MapBody graph={graph} onDrillIntoCycle={onDrillIntoCycle} />
      ) : (
        <TrailBody trail={trail} onDrillIntoCycle={onDrillIntoCycle} />
      )}
    </Card>
  )
}

function MapBody({
  graph,
  onDrillIntoCycle,
}: {
  graph: JobCycleGraphResponse | null
  onDrillIntoCycle?: (jobTypeId: number) => void
}) {
  if (!graph) return null
  const rootKey = `job_type:${graph.root_job_type_id}`
  const columns = layoutJobGraph({ nodes: graph.nodes, edges: graph.edges, rootKey })

  if (graph.edges.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground" data-testid="job-graph-map-empty">
        This job cycle has no nested cycles. Add a <code>job_cycle</code> link to a cell and it will
        appear here.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start gap-4" data-testid="job-graph-map-columns">
        {columns.map((column) => (
          <div
            key={column.depth}
            className="min-w-[180px] space-y-2"
            data-testid={`job-graph-column-${column.depth}`}
          >
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
              {column.depth === 0 ? 'This cycle' : `Nested · depth ${column.depth}`}
            </p>
            {column.nodes.map((node) => (
              <div key={node.key} className="space-y-1">
                <GraphNodeChip node={node} onDrillIntoCycle={onDrillIntoCycle} />
                <ul className="space-y-0.5 pl-3">
                  {edgesFromNode(graph.edges, node.key).map((edge) => (
                    <GraphEdgeRow key={edge.key} edge={edge} />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ))}
      </div>
      {graph.truncated ? (
        <p
          className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-900 dark:text-amber-100"
          data-testid="job-graph-map-truncated"
          role="status"
        >
          Nesting continues past depth {graph.depth}. This map shows the first {graph.depth}{' '}
          level(s) only.
        </p>
      ) : null}
    </div>
  )
}

function TrailBody({
  trail,
  onDrillIntoCycle,
}: {
  trail: JobAuditTrailResponse | null
  onDrillIntoCycle?: (jobTypeId: number) => void
}) {
  if (!trail) return null
  const index = buildGraphNodeIndex(trail.nodes)

  if (trail.paths.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground" data-testid="job-graph-trail-empty">
        No path to walk yet. Mark a cell as requiring evidence, or attach a document reference, and
        the walk will have somewhere to go.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-muted-foreground" data-testid="job-graph-trail-sample">
        Showing {trail.paths.length} of {trail.total_candidates} path(s).{' '}
        {trail.assure
          ? 'Assured: evidence is checked against Library / Document Control.'
          : 'Presence only: turn Freshness on to check attached evidence is still current.'}
      </p>
      <ol className="space-y-2" data-testid="job-graph-trail-paths">
        {trail.paths.map((path) => (
          <li
            key={path.cell_id}
            className="space-y-1 rounded-md border border-border p-2"
            data-testid={`job-graph-trail-path-${path.cell_id}`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium">
                {path.lane_name} · {path.step_name}
              </span>
              {path.requires_evidence ? (
                <span className="rounded-full border border-primary/40 bg-primary/10 px-1.5 py-0 text-[9px] uppercase tracking-wide text-primary">
                  Mandatory
                </span>
              ) : null}
              <span
                className={`rounded-full border px-1.5 py-0 text-[9px] uppercase tracking-wide ${readinessStateClasses(path.readiness.state)}`}
                data-testid={`job-graph-trail-readiness-${path.cell_id}`}
                data-readiness-state={path.readiness.state}
                title={readinessTitle(path.readiness)}
              >
                {readinessStateLabel(path.readiness.state)}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-1">
              {resolveTrailPathNodes(index, path.node_keys).map((node) => (
                <GraphNodeChip key={node.key} node={node} onDrillIntoCycle={onDrillIntoCycle} />
              ))}
            </div>
          </li>
        ))}
      </ol>
      {trail.truncated ? (
        <p
          className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-900 dark:text-amber-100"
          data-testid="job-graph-trail-truncated"
          role="status"
        >
          {trail.total_candidates - trail.paths.length} further path(s) were not walked. This is a
          sample, not a complete audit export.
        </p>
      ) : null}
    </div>
  )
}
